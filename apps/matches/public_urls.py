from django.urls import path

from .views import PublicBracketView, PublicMatchListView

urlpatterns = [
    path("matches/", PublicMatchListView.as_view(), name="public-match-list"),
    path("bracket/", PublicBracketView.as_view(), name="public-bracket-detail"),
]
