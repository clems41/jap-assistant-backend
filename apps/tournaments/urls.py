from django.urls import path

from apps.tournaments.views import (
    LastLeagueView,
    TournamentCategoryEnumView,
    TournamentDetailView,
    TournamentGenderEnumView,
    TournamentLeagueEnumView,
    TournamentListCreateView,
)

urlpatterns = [
    # Enum endpoints — fixed paths before parametric routes
    path("enums/categories/", TournamentCategoryEnumView.as_view(), name="tournament-enum-categories"),
    path("enums/leagues/", TournamentLeagueEnumView.as_view(), name="tournament-enum-leagues"),
    path("enums/genders/", TournamentGenderEnumView.as_view(), name="tournament-enum-genders"),
    # Last league pre-fill helper — fixed path before <int:pk>
    path("last-league/", LastLeagueView.as_view(), name="tournament-last-league"),
    # CRUD
    path("", TournamentListCreateView.as_view(), name="tournament-list"),
    path("<int:pk>/", TournamentDetailView.as_view(), name="tournament-detail"),
]
