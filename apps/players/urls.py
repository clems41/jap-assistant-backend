from django.urls import path

from .views import PairCSVImportView, PairDetailView, PairListCreateView

urlpatterns = [
    path("import/", PairCSVImportView.as_view(), name="pair-csv-import"),
    path("", PairListCreateView.as_view(), name="pair-list"),
    path("<int:pk>/", PairDetailView.as_view(), name="pair-detail"),
]
