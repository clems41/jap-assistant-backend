import unicodedata

from django.db import transaction

from apps.tournaments.models import Tournament

from ..models import FFTRanking, Pair, Player


def _normalize(name: str) -> str:
    """Normalize a name for fuzzy comparison: strip accents, replace hyphens with spaces, lowercase."""
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    return name.replace("-", " ").lower().strip()


def find_ranking(player: Player, tournament: Tournament) -> int | None:
    """Return the matched FFT ranking for a player, or None if ambiguous/not found."""
    norm_last = _normalize(player.last_name)
    norm_first = _normalize(player.first_name)

    qs = FFTRanking.objects.filter(last_name__iexact=player.last_name)
    if tournament.gender != Tournament.Gender.MIXED:
        qs = qs.filter(gender=tournament.gender)

    matches = [
        r
        for r in qs
        if _normalize(r.last_name) == norm_last and _normalize(r.first_name) == norm_first
    ]

    if len(matches) == 1:
        return matches[0].ranking
    if len(matches) > 1:
        league_matches = [r for r in matches if r.league == tournament.league]
        if len(league_matches) == 1:
            return league_matches[0].ranking
    return None


def fill_rankings_for_players(
    players: list[Player], tournament: Tournament, force: bool = False
) -> None:
    """Attempt a FFTRanking lookup for each player and persist the result.

    Args:
        players: Players to process.
        tournament: Used to filter FFTRanking by gender/league.
        force: If True, overwrite existing rankings. If False, only fill
               players whose ranking is currently None.

    Note — intentional overwrite on force=True:
        When force=True the caller signals that the player's identity data
        (last_name / first_name) may have just changed, so the previous
        ranking is stale and should be replaced by a fresh FFT lookup.
        This is the desired behaviour when the user edits a player's name
        via the API: the system re-resolves the ranking automatically.
        A ranking that was set manually (and whose player data was NOT
        modified in the same request) is never overwritten because those
        players are passed with force=False.
    """
    to_save = []
    for player in players:
        if force or player.ranking is None:
            matched = find_ranking(player, tournament)
            if matched is not None:
                player.ranking = matched
                to_save.append(player)
    if to_save:
        Player.objects.bulk_update(to_save, ["ranking", "updated_at"])


@transaction.atomic
def match_and_update_rankings(tournament: Tournament) -> list[Pair]:
    pairs = list(
        Pair.objects.filter(tournament=tournament).select_related("player1", "player2")
    )

    players_to_save: list[Player] = []
    seen_player_ids: set[int] = set()

    for pair in pairs:
        for player in [pair.player1, pair.player2]:
            if player.ranking is None and player.pk not in seen_player_ids:
                matched = find_ranking(player, tournament)
                if matched is not None:
                    player.ranking = matched
                    players_to_save.append(player)
                seen_player_ids.add(player.pk)

    if players_to_save:
        Player.objects.bulk_update(players_to_save, ["ranking", "updated_at"])

    pairs_to_save: list[Pair] = []
    for pair in pairs:
        if (
            pair.weight is None
            and pair.player1.ranking is not None
            and pair.player2.ranking is not None
        ):
            pair.weight = pair.player1.ranking + pair.player2.ranking
            pairs_to_save.append(pair)

    if pairs_to_save:
        Pair.objects.bulk_update(pairs_to_save, ["weight", "updated_at"])

    tournament.recompute_status()
    return pairs
