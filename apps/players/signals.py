from django.db.models import F
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.players.models import Pair


@receiver(post_save, sender=Pair)
def increment_pairs_count(sender: type, instance: Pair, created: bool, **kwargs: object) -> None:
    if created:
        instance.tournament.__class__.objects.filter(
            pk=instance.tournament_id
        ).update(pairs_count=F("pairs_count") + 1)


@receiver(post_delete, sender=Pair)
def decrement_pairs_count(sender: type, instance: Pair, **kwargs: object) -> None:
    instance.tournament.__class__.objects.filter(
        pk=instance.tournament_id
    ).update(pairs_count=F("pairs_count") - 1)
