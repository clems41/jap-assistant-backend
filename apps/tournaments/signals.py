"""
Django signals that trigger Tournament.recompute_status().

Registered in TournamentsConfig.ready() to avoid import-time side effects.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


def _recompute_for_pair(pair) -> None:
    pair.tournament.recompute_status()


def register_signals() -> None:
    """Attach all signal handlers. Called once from TournamentsConfig.ready()."""
    from apps.players.models import Pair, Player

    @receiver(post_save, sender=Pair, dispatch_uid="tournaments.pair_post_save")
    def on_pair_saved(sender, instance, **kwargs) -> None:
        _recompute_for_pair(instance)

    @receiver(post_delete, sender=Pair, dispatch_uid="tournaments.pair_post_delete")
    def on_pair_deleted(sender, instance, **kwargs) -> None:
        _recompute_for_pair(instance)

    @receiver(post_save, sender=Player, dispatch_uid="tournaments.player_post_save")
    def on_player_saved(sender, instance, **kwargs) -> None:
        # Recompute for every tournament where this player is part of a pair
        # whose weight may have been nullified following a ranking change.
        from apps.players.models import Pair as PairModel

        pairs = PairModel.objects.filter(
            player1=instance
        ) | PairModel.objects.filter(player2=instance)

        seen = set()
        for pair in pairs:
            tid = pair.tournament_id
            if tid not in seen:
                seen.add(tid)
                pair.tournament.recompute_status()
