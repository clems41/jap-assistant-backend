import factory
from factory.django import DjangoModelFactory

from apps.tournaments.models import Tournament


class TournamentFactory(DjangoModelFactory):
    name = factory.Sequence(lambda n: f"Tournament {n}")
    category = Tournament.Category.P100
    start_date = factory.Faker("date_object")
    location = factory.Faker("city")
    league = Tournament.League.ILE_DE_FRANCE
    gender = Tournament.Gender.MIXED

    class Meta:
        model = Tournament
