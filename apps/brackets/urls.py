from django.urls import path

from .views import BracketStateView

urlpatterns = [
    path("", BracketStateView.as_view(), name="bracket-state"),
]
