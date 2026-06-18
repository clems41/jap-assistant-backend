from apps.tournaments.models import Tournament

from .models import ROUNDS_BY_DIMENSION, Bracket, Match


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
        new_entrants = getattr(
            main_bracket, f"nb_pair_round_{round_size}", 0
        )
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
