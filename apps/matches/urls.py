from django.urls import path

from .views import BracketView

urlpatterns = [
    path("bracket/", BracketView.as_view()),
]
