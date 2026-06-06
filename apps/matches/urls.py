from django.urls import path

from .views import BracketView, MatchScoreView

urlpatterns = [
    path("bracket/", BracketView.as_view()),
    path("matches/<int:match_id>/score/", MatchScoreView.as_view()),
]
