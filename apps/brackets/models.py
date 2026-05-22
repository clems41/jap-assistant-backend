from django.db import models

from apps.common.models import TimeStampedModel
from apps.players.models import Pair
from apps.tournaments.models import Tournament

DIMENSION_CHOICES = [(4, "4"), (8, "8"), (16, "16"), (32, "32"), (64, "64")]


class BracketState(TimeStampedModel):
    tournament = models.OneToOneField(
        Tournament,
        on_delete=models.CASCADE,
        related_name="bracket_state",
    )
    dimension = models.PositiveSmallIntegerField(choices=DIMENSION_CHOICES)
    nb_top_seeds = models.PositiveSmallIntegerField(default=0)

    def __str__(self) -> str:
        return f"BracketState(tournament={self.tournament_id}, dim={self.dimension})"


class BracketSlot(TimeStampedModel):
    bracket_state = models.ForeignKey(
        BracketState,
        on_delete=models.CASCADE,
        related_name="slots",
    )
    slot_title = models.CharField(max_length=20)
    score = models.CharField(max_length=50, blank=True, null=True)
    game_format = models.CharField(
        max_length=2,
        choices=Tournament.GameFormat.choices,
        blank=True,
        null=True,
    )
    pair = models.ForeignKey(
        Pair,
        on_delete=models.CASCADE,
        related_name="bracket_slots",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["bracket_state", "slot_title"],
                name="uq_slot_per_bracket",
            ),
            models.UniqueConstraint(
                fields=["bracket_state", "pair"],
                name="uq_pair_per_bracket",
            ),
        ]

    def __str__(self) -> str:
        return f"BracketSlot({self.slot_title}, pair={self.pair_id})"
