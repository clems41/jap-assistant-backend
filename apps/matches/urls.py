from django.urls import path

from .views import BracketPlacementView, BracketView, MatchScoreView, MatchStartView

urlpatterns = [
    path("bracket/", BracketView.as_view()),
    path("bracket/placement/", BracketPlacementView.as_view()),
    path("matches/<int:match_id>/score/", MatchScoreView.as_view()),
    path("matches/<int:match_id>/start/", MatchStartView.as_view()),
]
