from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class Tournament(TimeStampedModel):
    """Represents a padel tournament managed by a JAP."""

    class Category(models.TextChoices):
        P25 = "P25", "P25"
        P50 = "P50", "P50"
        P100 = "P100", "P100"
        P250 = "P250", "P250"
        P500 = "P500", "P500"
        P1000 = "P1000", "P1000"
        P2000 = "P2000", "P2000"

    class League(models.TextChoices):
        AUVERGNE_RHONE_ALPES = "Auvergne-Rhône-Alpes", "Auvergne-Rhône-Alpes"
        BOURGOGNE_FRANCHE_COMTE = "Bourgogne-Franche-Comté", "Bourgogne-Franche-Comté"
        BRETAGNE = "Bretagne", "Bretagne"
        CENTRE_VAL_DE_LOIRE = "Centre Val de Loire", "Centre Val de Loire"
        CORSE = "Corse", "Corse"
        GRAND_EST = "Grand Est", "Grand Est"
        GUADELOUPE = "Guadeloupe", "Guadeloupe"
        GUYANE = "Guyane", "Guyane"
        HAUTS_DE_FRANCE = "Hauts de France", "Hauts de France"
        ILE_DE_FRANCE = "Ile de France", "Ile de France"
        MARTINIQUE = "Martinique", "Martinique"
        NORMANDIE = "Normandie", "Normandie"
        NOUVELLE_AQUITAINE = "Nouvelle Aquitaine", "Nouvelle Aquitaine"
        NOUVELLE_CALEDONIE = "Nouvelle Calédonie", "Nouvelle Calédonie"
        OCCITANIE = "Occitanie", "Occitanie"
        PAYS_DE_LA_LOIRE = "Pays de la Loire", "Pays de la Loire"
        PROVENCE_ALPES_COTES_AZUR = "Provence-Alpes-Côtes d'Azur", "Provence-Alpes-Côtes d'Azur"
        REUNION = "Réunion", "Réunion"

    class Gender(models.TextChoices):
        MALE = "Homme", "Homme"
        FEMALE = "Femme", "Femme"
        MIXED = "Mixte", "Mixte"

    class GameFormat(models.TextChoices):
        A1 = "A1", "A1 : 3 sets à 6 jeux, jeu décisif à 6-6"
        A2 = "A2", "A2 : 3 sets à 6 jeux, point décisif, jeu décisif à 6-6"
        B1 = "B1", "B1 : 2 sets à 6 jeux, jeu décisif à 6-6, 3ème set = super jeu décisif à 10 points"
        B2 = "B2", "B2 : 2 sets à 6 jeux, point décisif, jeu décisif à 6-6, 3ème set = super jeu décisif à 10 points"
        C1 = "C1", "C1 : 2 sets à 4 jeux, jeu décisif à 4-4, 3ème set = super jeu décisif à 10 points"
        C2 = "C2", "C2 : 2 sets à 4 jeux, point décisif, jeu décisif à 4-4, 3ème set = super jeu décisif à 10 points"
        D1 = "D1", "D1 : 1 set à 9 jeux, jeu décisif à 8-8"
        D2 = "D2", "D2 : 1 set à 9 jeux, point décisif, jeu décisif à 8-8"
        E = "E", "E : 1 super jeu décisif à 10 points"
        F = "F", "F : 1 set à 4 jeux, point décisif, jeu décisif à 3-3"

    class Configuration(models.TextChoices):
        TMC = "TMC", "Tournoi Multi Chance (TMC)"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        SET = "SET", "Configuré"
        READY = "READY", "Prêt"
        STARTED = "STARTED", "En cours"
        FINISHED = "FINISHED", "Terminé"

    GAME_FORMAT_DEFAULT_DURATIONS: dict[str, int] = {
        "A1": 100,
        "A2": 90,
        "B1": 70,
        "B2": 60,
        "C1": 50,
        "C2": 45,
        "D1": 50,
        "D2": 45,
        "E": 20,
        "F": 25,
    }

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tournaments",
    )
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=10, choices=Category.choices)
    start_date = models.DateField()
    location = models.CharField(max_length=255)
    league = models.CharField(max_length=50, choices=League.choices)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    game_format = models.CharField(max_length=2, choices=GameFormat.choices, blank=True, default="")
    configuration = models.CharField(max_length=20, choices=Configuration.choices, null=True, blank=True)
    estimated_match_duration = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    pairs_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["start_date", "name"]
        verbose_name = "tournament"
        verbose_name_plural = "tournaments"

    def __str__(self) -> str:
        return self.name

    def recompute_status(self) -> None:
        """Recompute and persist the tournament status based on current state.

        Never downgrades STARTED or FINISHED — those are terminal states
        managed outside this method.
        """
        if self.status in (self.Status.STARTED, self.Status.FINISHED):
            return

        new_status = self._compute_status()
        if new_status != self.status:
            self.status = new_status
            self.save(update_fields=["status", "updated_at"])

    def _compute_status(self) -> str:
        """Return the status that reflects the current data, without persisting.

        Note: SET → READY transition is not yet implemented.
        READY remains in Status.choices for future use.
        """
        if not self._conditions_for_set_are_met():
            return self.Status.DRAFT

        return self.Status.SET

    def _conditions_for_set_are_met(self) -> bool:
        """Return True when the tournament has >= 2 fully weighted pairs,
        a configuration and a game_format."""
        if not self.configuration or not self.game_format:
            return False

        pairs = self.pairs.all()
        if pairs.count() < 2:
            return False

        return not pairs.filter(weight__isnull=True).exists()


class TimeSlot(TimeStampedModel):
    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="time_slots",
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    courts_available = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["start_time"]

    def __str__(self) -> str:
        return f"{self.start_time:%H:%M} – {self.end_time:%H:%M} ({self.courts_available} courts)"
