import factory
from factory.django import DjangoModelFactory

from apps.players.models import Pair, Player
from apps.tournaments.tests.factories import TournamentFactory


class PlayerFactory(DjangoModelFactory):
    class Meta:
        model = Player
        django_get_or_create = ("license_number",)

    last_name = factory.Faker("last_name")
    first_name = factory.Faker("first_name")
    license_number = factory.Sequence(lambda n: f"LIC{n:07d}")
    phone = factory.Faker("phone_number")
    ranking = factory.Faker("random_int", min=1, max=1000)


class PairFactory(DjangoModelFactory):
    class Meta:
        model = Pair

    tournament = factory.SubFactory(TournamentFactory)
    player1 = factory.SubFactory(PlayerFactory)
    player2 = factory.SubFactory(PlayerFactory)
    weight = factory.Faker("pyfloat", min_value=100, max_value=1000, right_digits=1)
