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

    class Meta:
        ordering = ["start_date", "name"]
        verbose_name = "tournament"
        verbose_name_plural = "tournaments"

    def __str__(self) -> str:
        return self.name
