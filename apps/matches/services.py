import heapq
from datetime import datetime, timedelta

from django.utils import timezone

from apps.tournaments.models import Tournament

from .models import ROUND_BY_SIZE, ROUNDS_BY_DIMENSION, Bracket, Match

COURT_CHANGEOVER = timedelta(minutes=5)


def generate_match_tree(bracket: Bracket, game_format: str) -> Match:
    """Build the match tree bottom-up. Returns the root (finale) match."""
    rounds = ROUNDS_BY_DIMENSION[bracket.dimension]

    current_round_matches: list[Match] = []

    for i, round_name in enumerate(rounds):
        num_matches = bracket.dimension // (2 ** (i + 1))

        if i == 0:
            new_matches = [
                Match.objects.create(
                    bracket=bracket,
                    round=round_name,
                    match_number=j + 1,
                    game_format=game_format,
                )
                for j in range(num_matches)
            ]
        else:
            prev = current_round_matches
            new_matches = []
            for j in range(num_matches):
                m = Match.objects.create(
                    bracket=bracket,
                    round=round_name,
                    match_number=j + 1,
                    game_format=game_format,
                    child1=prev[2 * j],
                    child2=prev[2 * j + 1],
                )
                new_matches.append(m)

        current_round_matches = new_matches

    return current_round_matches[0]


def place_top_seeds(bracket: Bracket, tournament: Tournament) -> None:
    """Place TS1/TS2 (têtes de série) into the main bracket per FFT rules:
    TS1 is the pair with the lowest weight, TS2 the second-lowest. They
    enter at the round corresponding to the smallest nonzero
    nb_pair_round_X, with TS1 in pair2 of that round's last match and TS2
    in pair1 of its first match.
    """
    round_size = next(
        (
            size
            for size in sorted(ROUND_BY_SIZE)
            if getattr(bracket, f"nb_pair_round_{size}") > 0
        ),
        None,
    )
    if round_size is None:
        return

    top_seed, second_seed = tournament.pairs.order_by("weight", "id")[:2]
    round_name = ROUND_BY_SIZE[round_size]
    num_matches = round_size // 2

    bottom_match = Match.objects.get(
        bracket=bracket, round=round_name, match_number=num_matches
    )
    bottom_match.pair2 = top_seed
    bottom_match.save(update_fields=["pair2", "updated_at"])

    top_match = Match.objects.get(bracket=bracket, round=round_name, match_number=1)
    top_match.pair1 = second_seed
    top_match.save(update_fields=["pair1", "updated_at"])


def generate_classification_brackets(
    main_bracket: Bracket, tournament: Tournament
) -> list[Bracket]:
    """Auto-generate the top-level classification brackets derived from the
    main bracket's rounds (Step A), then recursively cascade each of them
    into their own children (Step B).

    Processes rounds from earliest to latest (excluding the FINALE, which
    never produces a classification bracket: its 2 finalists play the main
    bracket's own final).
    """
    dimension = main_bracket.dimension
    rounds = ROUNDS_BY_DIMENSION[dimension][:-1]

    created: list[Bracket] = []
    carried_winners = 0
    remaining_pool = tournament.pairs_count

    for index, round_name in enumerate(rounds):
        round_size = dimension // (2**index)
        new_entrants = getattr(main_bracket, f"nb_pair_round_{round_size}", 0)
        entering = carried_winners + new_entrants
        real_matches = entering // 2

        if real_matches > 0:
            classification_bracket = Bracket.objects.create(
                parent=main_bracket,
                tournament=tournament,
                dimension=real_matches,
                source_round=round_name,
                start_place=remaining_pool - real_matches + 1,
                end_place=remaining_pool,
            )
            generate_match_tree(classification_bracket, tournament.game_format)
            created.append(classification_bracket)
            _cascade_classification(classification_bracket, tournament)
            remaining_pool -= real_matches

        carried_winners = real_matches

    return created


def _assign_order(bracket: Bracket, start: int, matches_to_update: list[Match]) -> int:
    """Recursively flatten `bracket` and its classification children into a
    single default order, biggest round to smallest, ending in FINALE, with
    each classification bracket's matches inserted immediately after the
    round they derive from. Returns the next free order value after this
    subtree, so callers can chain across siblings/recursion.
    """
    order = start
    rounds = ROUNDS_BY_DIMENSION[bracket.dimension]
    matches_by_round: dict[str, list[Match]] = {}
    for m in bracket.matches.all():
        matches_by_round.setdefault(m.round, []).append(m)
    children_by_source_round = {c.source_round: c for c in bracket.children.all()}

    for round_name in rounds:
        round_matches = sorted(
            matches_by_round.get(round_name, []), key=lambda m: m.match_number
        )
        for m in round_matches:
            m.order = order
            order += 1
        matches_to_update.extend(round_matches)

        child = children_by_source_round.get(round_name)
        if child is not None:
            order = _assign_order(child, order, matches_to_update)

    return order


def assign_match_order(main_bracket: Bracket) -> None:
    """Assign the default match order for `main_bracket` and all of its
    classification brackets (recursively), then persist it in one query.
    """
    matches_to_update: list[Match] = []
    _assign_order(main_bracket, 1, matches_to_update)
    Match.objects.bulk_update(matches_to_update, ["order"])


def _cascade_classification(bracket: Bracket, tournament: Tournament) -> None:
    """Recursively cascade a classification bracket into its own children
    (Step B). Processes from the round closest to this bracket's own final
    (producing 2 losers) outward to the round furthest away (producing D/2
    losers), since start_place arithmetic depends on this order.
    """
    dimension = bracket.dimension
    if dimension <= 2:
        return

    start_place = bracket.start_place
    rounds = ROUNDS_BY_DIMENSION[dimension][:-1]

    ms = [2**i for i in range(1, len(rounds) + 1)]
    for m, round_name in zip(ms, reversed(rounds), strict=True):
        child = Bracket.objects.create(
            parent=bracket,
            tournament=tournament,
            dimension=m,
            source_round=round_name,
            start_place=start_place + m,
            end_place=start_place + 2 * m - 1,
        )
        generate_match_tree(child, tournament.game_format)
        _cascade_classification(child, tournament)


def compute_estimated_start_times(tournament: Tournament) -> dict[int, datetime]:
    """Return {match_id: estimated_start_at} for every UPCOMING match of
    `tournament` that can be estimated. Matches that can't be estimated
    (missing estimated_match_duration, no TimeSlot, or no remaining
    scheduled court capacity) are simply absent from the returned dict.

    Simulates a "queue of courts" (a capacity counter, not physically
    identified courts) being freed up over the day as STARTED/FINISHED
    matches end, then assigns each UPCOMING match (in `order`) to the
    earliest available slot in that queue.
    """
    duration = tournament.estimated_match_duration
    if duration is None:
        return {}
    duration_delta = timedelta(minutes=duration)

    time_slot_periods = sorted(
        (
            (
                timezone.make_aware(
                    datetime.combine(tournament.start_date, ts.start_time)
                ),
                timezone.make_aware(
                    datetime.combine(tournament.start_date, ts.end_time)
                ),
                ts.courts_available,
            )
            for ts in tournament.time_slots.all()
        ),
        key=lambda period: period[0],
    )
    if not time_slot_periods:
        return {}

    def capacity_at(t: datetime) -> int:
        for start, end, courts in time_slot_periods:
            if start <= t < end:
                return courts
        return 0

    now = timezone.now()

    effective_now = None
    for start, _end, courts in time_slot_periods:
        candidate = max(now, start)
        if courts > 0 and capacity_at(candidate) > 0:
            effective_now = candidate
            break
    if effective_now is None:
        return {}

    capacity_now = capacity_at(effective_now)

    started_matches = list(
        Match.objects.filter(
            bracket__tournament=tournament,
            disabled=False,
            status=Match.Status.STARTED,
        )
    )

    release_heap: list[datetime] = []
    for m in started_matches:
        release_at = (m.started_at or effective_now) + duration_delta + COURT_CHANGEOVER
        heapq.heappush(release_heap, release_at)

    free_count = max(capacity_now - len(started_matches), 0)
    if free_count > 0:
        # Exclude NULL finished_at (defensive: legacy/inconsistent data)
        # explicitly — Postgres sorts NULLs first on DESC by default, which
        # would otherwise wrongly treat them as "most recently finished".
        recent_finished = list(
            Match.objects.filter(
                bracket__tournament=tournament,
                disabled=False,
                status=Match.Status.FINISHED,
                finished_at__isnull=False,
            ).order_by("-finished_at")[:free_count]
        )
        for m in recent_finished:
            heapq.heappush(release_heap, m.finished_at + COURT_CHANGEOVER)
        for _ in range(free_count - len(recent_finished)):
            heapq.heappush(release_heap, effective_now)

    future_slot_changes: list[tuple[datetime, int]] = []
    previous_courts = capacity_now
    for start, _end, courts in time_slot_periods:
        if start > effective_now:
            extra_courts = courts - previous_courts
            if extra_courts > 0:
                future_slot_changes.append((start, extra_courts))
            previous_courts = courts
    future_slot_changes.sort(key=lambda change: change[0])

    upcoming_matches = Match.objects.filter(
        bracket__tournament=tournament,
        disabled=False,
        status=Match.Status.UPCOMING,
    ).order_by("order")

    day_end = time_slot_periods[-1][1]

    result: dict[int, datetime] = {}
    change_index = 0
    for match in upcoming_matches:
        while (
            release_heap
            and change_index < len(future_slot_changes)
            and future_slot_changes[change_index][0] <= release_heap[0]
        ):
            change_start, extra_courts = future_slot_changes[change_index]
            for _ in range(extra_courts):
                heapq.heappush(release_heap, change_start)
            change_index += 1

        if not release_heap:
            break

        release = heapq.heappop(release_heap)
        start_at = max(release, now)
        if start_at >= day_end:
            break

        result[match.id] = start_at
        heapq.heappush(release_heap, start_at + duration_delta)

    return result
