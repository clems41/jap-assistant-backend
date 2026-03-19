from django.urls import path

from .views import (
    PairCSVImportView,
    PairDetailView,
    PairListCreateView,
    RankingMatchingView,
)

urlpatterns = [
    path("import/", PairCSVImportView.as_view(), name="pair-csv-import"),
    path("ranking-matching/", RankingMatchingView.as_view(), name="pair-ranking-matching"),
    path("", PairListCreateView.as_view(), name="pair-list"),
    path("<int:pk>/", PairDetailView.as_view(), name="pair-detail"),
]
