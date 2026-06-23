from django.urls import path

from .views import PublicPairListView

urlpatterns = [
    path("pairs/", PublicPairListView.as_view(), name="public-pair-list"),
]
