from django.urls import path

from apps.tournaments.views import (
    InformationsView,
    TimeSlotDetailView,
    TimeSlotListCreateView,
    TournamentCategoryEnumView,
    TournamentConfigurationEnumView,
    TournamentDetailView,
    TournamentGameFormatDurationView,
    TournamentGameFormatEnumView,
    TournamentGenderEnumView,
    TournamentLeagueEnumView,
    TournamentListCreateView,
    TournamentSetReadinessView,
)

urlpatterns = [
    # Enum endpoints — fixed paths before parametric routes
    path(
        "enums/categories/",
        TournamentCategoryEnumView.as_view(),
        name="tournament-enum-categories",
    ),
    path(
        "enums/leagues/",
        TournamentLeagueEnumView.as_view(),
        name="tournament-enum-leagues",
    ),
    path(
        "enums/genders/",
        TournamentGenderEnumView.as_view(),
        name="tournament-enum-genders",
    ),
    path(
        "enums/game-formats/",
        TournamentGameFormatEnumView.as_view(),
        name="tournament-enum-game-formats",
    ),
    path(
        "enums/game-format-durations/",
        TournamentGameFormatDurationView.as_view(),
        name="tournament-enum-game-format-durations",
    ),
    path(
        "enums/configurations/",
        TournamentConfigurationEnumView.as_view(),
        name="tournament-enum-configurations",
    ),
    # Informations pre-fill helper — fixed path before <int:pk>
    path("informations/", InformationsView.as_view(), name="tournament-informations"),
    # CRUD
    path("", TournamentListCreateView.as_view(), name="tournament-list"),
    path("<int:pk>/", TournamentDetailView.as_view(), name="tournament-detail"),
    path(
        "<int:pk>/set-readiness/",
        TournamentSetReadinessView.as_view(),
        name="tournament-set-readiness",
    ),
    # Time slots (sub-collection)
    path(
        "<int:tournament_id>/time-slots/",
        TimeSlotListCreateView.as_view(),
        name="tournament-time-slot-list",
    ),
    path(
        "<int:tournament_id>/time-slots/<int:pk>/",
        TimeSlotDetailView.as_view(),
        name="tournament-time-slot-detail",
    ),
]
