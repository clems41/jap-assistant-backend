from django.db import models

from apps.common.models import TimeStampedModel
from apps.tournaments.models import Tournament


class Round(models.TextChoices):
    FINALE = "FINALE", "Finale"
    DEMI_FINALE = "DEMI_FINALE", "Demi-finale"
    QUART_DE_FINALE = "QUART_DE_FINALE", "Quart de finale"
    HUITIEME_DE_FINALE = "HUITIEME_DE_FINALE", "Huitième de finale"
    SEIZIEME_DE_FINALE = "SEIZIEME_DE_FINALE", "Seizième de finale"
    TRENTE_DEUXIEME_DE_FINALE = "TRENTE_DEUXIEME_DE_FINALE", "32ème de finale"


ROUNDS_BY_DIMENSION: dict[int, list[str]] = {
    8: [
        Round.QUART_DE_FINALE,
        Round.DEMI_FINALE,
        Round.FINALE,
    ],
    16: [
        Round.HUITIEME_DE_FINALE,
        Round.QUART_DE_FINALE,
        Round.DEMI_FINALE,
        Round.FINALE,
    ],
    32: [
        Round.SEIZIEME_DE_FINALE,
        Round.HUITIEME_DE_FINALE,
        Round.QUART_DE_FINALE,
        Round.DEMI_FINALE,
        Round.FINALE,
    ],
    64: [
        Round.TRENTE_DEUXIEME_DE_FINALE,
        Round.SEIZIEME_DE_FINALE,
        Round.HUITIEME_DE_FINALE,
        Round.QUART_DE_FINALE,
        Round.DEMI_FINALE,
        Round.FINALE,
    ],
}


class Bracket(TimeStampedModel):
    DIMENSION_CHOICES = [(8, "8"), (16, "16"), (32, "32"), (64, "64")]

    tournament = models.OneToOneField(
        Tournament,
        on_delete=models.CASCADE,
        related_name="bracket",
    )
    dimension = models.PositiveSmallIntegerField(choices=DIMENSION_CHOICES)
    nb_top_seeds = models.PositiveSmallIntegerField()

    def __str__(self) -> str:
        return f"Bracket {self.dimension} — {self.tournament}"


class Match(TimeStampedModel):
    bracket = models.ForeignKey(
        Bracket,
        on_delete=models.CASCADE,
        related_name="matches",
    )
    pair1 = models.ForeignKey(
        "players.Pair",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="matches_as_pair1",
    )
    pair2 = models.ForeignKey(
        "players.Pair",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="matches_as_pair2",
    )
    round = models.CharField(max_length=30, choices=Round.choices)
    match_number = models.PositiveSmallIntegerField()
    game_format = models.CharField(
        max_length=2,
        choices=Tournament.GameFormat.choices,
        blank=True,
        default="",
    )
    score = models.CharField(max_length=50, blank=True, default="")
    child1 = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="parent_as_child1",
    )
    child2 = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="parent_as_child2",
    )

    class Meta:
        ordering = ["round", "match_number"]

    def __str__(self) -> str:
        return f"{self.get_round_display()} #{self.match_number}"
