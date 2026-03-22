from datetime import date, datetime, time, timedelta

import factory
from factory.django import DjangoModelFactory

from apps.tournaments.models import TimeSlot, Tournament
from apps.users.tests.factories import UserFactory


class TournamentFactory(DjangoModelFactory):
    owner = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Tournament {n}")
    category = Tournament.Category.P100
    start_date = factory.Faker("date_object")
    location = factory.Faker("city")
    league = Tournament.League.ILE_DE_FRANCE
    gender = Tournament.Gender.MIXED

    class Meta:
        model = Tournament


class TimeSlotFactory(DjangoModelFactory):
    tournament = factory.SubFactory(TournamentFactory)
    start_time = factory.LazyFunction(lambda: time(9, 0))
    end_time = factory.LazyAttribute(
        lambda obj: (
            datetime.combine(date.today(), obj.start_time) + timedelta(hours=1)
        ).time()
    )
    courts_available = 4

    class Meta:
        model = TimeSlot
