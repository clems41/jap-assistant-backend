from django.urls import path

from apps.tournaments.views import (
    TournamentCategoryEnumView,
    TournamentDetailView,
    TournamentGenderEnumView,
    TournamentLeagueEnumView,
    TournamentListCreateView,
)

urlpatterns = [
    # Enum endpoints — fixed paths before parametric routes
    path("enums/categories", TournamentCategoryEnumView.as_view(), name="tournament-enum-categories"),
    path("enums/leagues", TournamentLeagueEnumView.as_view(), name="tournament-enum-leagues"),
    path("enums/genders", TournamentGenderEnumView.as_view(), name="tournament-enum-genders"),
    # CRUD
    path("", TournamentListCreateView.as_view(), name="tournament-list"),
    path("<int:pk>", TournamentDetailView.as_view(), name="tournament-detail"),
]
