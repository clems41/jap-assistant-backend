from django.db import models

from apps.common.models import TimeStampedModel
from apps.tournaments.models import Tournament


class Player(TimeStampedModel):
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    license_number = models.CharField(max_length=50, unique=True)
    phone = models.CharField(max_length=50, blank=True, default="")
    ranking = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name} ({self.license_number})"


class Pair(TimeStampedModel):
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="pairs",
    )
    player1 = models.ForeignKey(
        Player,
        on_delete=models.PROTECT,
        related_name="pairs_as_player1",
    )
    player2 = models.ForeignKey(
        Player,
        on_delete=models.PROTECT,
        related_name="pairs_as_player2",
    )
    weight = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tournament", "player1"],
                name="unique_tournament_player1",
            ),
            models.UniqueConstraint(
                fields=["tournament", "player2"],
                name="unique_tournament_player2",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.player1} / {self.player2} ({self.tournament})"
