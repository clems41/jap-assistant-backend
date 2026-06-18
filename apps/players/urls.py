from django.urls import path

from .views import (
    PairDetailView,
    PairImportView,
    PairListCreateView,
    RankingMatchingView,
)

urlpatterns = [
    path("import/", PairImportView.as_view(), name="pair-import"),
    path("ranking-matching/", RankingMatchingView.as_view(), name="pair-ranking-matching"),
    path("", PairListCreateView.as_view(), name="pair-list"),
    path("<int:pk>/", PairDetailView.as_view(), name="pair-detail"),
]
