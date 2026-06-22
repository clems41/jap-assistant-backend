from django.urls import path

from apps.tournaments.views import PublicTournamentDetailView

urlpatterns = [
    path("", PublicTournamentDetailView.as_view(), name="public-tournament-detail"),
]
