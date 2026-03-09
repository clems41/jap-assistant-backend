"""
WebSocket URL routing.
Add your Channels consumers here as the project grows.
"""
from django.urls import path

# Example: from apps.tournaments.consumers import TournamentConsumer

websocket_urlpatterns = [
    # path("ws/tournaments/<str:tournament_id>/", TournamentConsumer.as_asgi()),
]
