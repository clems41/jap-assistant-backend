import factory
from factory.django import DjangoModelFactory

from apps.matches.models import Bracket, Match, Round
from apps.tournaments.tests.factories import TournamentFactory


class BracketFactory(DjangoModelFactory):
    class Meta:
        model = Bracket

    tournament = factory.SubFactory(TournamentFactory)
    dimension = 8


class MatchFactory(DjangoModelFactory):
    class Meta:
        model = Match

    bracket = factory.SubFactory(BracketFactory)
    round = Round.FINALE
    match_number = 1
    game_format = ""
    score = ""
    pair1 = None
    pair2 = None
    child1 = None
    child2 = None
