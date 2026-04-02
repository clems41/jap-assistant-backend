import factory
from factory.django import DjangoModelFactory

from apps.brackets.models import BracketSlot, BracketState
from apps.players.tests.factories import PairFactory
from apps.tournaments.tests.factories import TournamentFactory


class BracketStateFactory(DjangoModelFactory):
    class Meta:
        model = BracketState

    tournament = factory.SubFactory(TournamentFactory)
    dimension = 16
    nb_top_seeds = 0


class BracketSlotFactory(DjangoModelFactory):
    class Meta:
        model = BracketSlot

    bracket_state = factory.SubFactory(BracketStateFactory)
    slot_title = factory.Sequence(lambda n: f"R16 #{n + 1}")
    pair = factory.SubFactory(PairFactory)
