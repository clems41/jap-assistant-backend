from django.db import transaction

from apps.tournaments.models import Tournament

from ..models import FFTRanking, Pair, Player


def _find_ranking(player: Player, tournament: Tournament) -> int | None:
    """Return the matched FFT ranking for a player, or None if ambiguous/not found."""
    qs = FFTRanking.objects.filter(
        last_name__iexact=player.last_name,
        first_name__iexact=player.first_name,
    )
    if tournament.gender != Tournament.Gender.MIXED:
        qs = qs.filter(gender=tournament.gender)

    count = qs.count()
    if count == 1:
        return qs.first().ranking
    if count > 1:
        league_qs = qs.filter(league=tournament.league)
        if league_qs.count() == 1:
            return league_qs.first().ranking
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
        if pair.player1.ranking is not None and pair.player2.ranking is not None:
            pair.weight = pair.player1.ranking + pair.player2.ranking
            pairs_to_save.append(pair)

    if pairs_to_save:
        Pair.objects.bulk_update(pairs_to_save, ["weight", "updated_at"])

    return pairs
