import unicodedata

from django.db import transaction

from apps.tournaments.models import Tournament

from ..models import FFTRanking, Pair, Player


def _normalize(name: str) -> str:
    """Normalize a name for fuzzy comparison: strip accents, replace hyphens with spaces, lowercase."""
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    return name.replace("-", " ").lower().strip()


def _find_ranking(player: Player, tournament: Tournament) -> int | None:
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
                matched = _find_ranking(player, tournament)
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

    return pairs
