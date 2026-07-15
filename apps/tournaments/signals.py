"""
Django signals that trigger Tournament.recompute_status().

Registered via `import apps.tournaments.signals` in TournamentsConfig.ready()
(mirrors apps.players.signals). Receivers MUST be module-level functions, not
closures created inside a function: Python only executes a module's body once
(cached in sys.modules), so module-level `@receiver` decorators are immune to
AppConfig.ready() running more than once in the same process. A previous
version defined these as closures inside a register_signals() function called
from ready() — if ready() ran twice, that function body re-executed, creating
duplicate receivers for Tournament/Player that dispatch_uid dedup couldn't
always catch, silently breaking the automatic status recompute in production.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.players.models import Pair, Player
from apps.tournaments.models import Tournament


def _recompute_for_pair(pair: Pair) -> None:
    pair.tournament.recompute_status()


@receiver(
    post_save,
    sender=Tournament,
    dispatch_uid="tournaments.tournament_post_save",
)
def on_tournament_saved(sender, instance, update_fields, **kwargs) -> None:
    # Guard: recompute_status() saves with these exact fields — skip to avoid recursion
    if update_fields and frozenset(update_fields) == frozenset(["status", "updated_at"]):
        return
    instance.recompute_status()


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
    pairs = Pair.objects.filter(player1=instance) | Pair.objects.filter(player2=instance)

    seen = set()
    for pair in pairs:
        tid = pair.tournament_id
        if tid not in seen:
            seen.add(tid)
            pair.tournament.recompute_status()
