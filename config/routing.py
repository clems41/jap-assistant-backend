"""
WebSocket URL routing.
Add your Channels consumers here as the project grows.
"""

from django.urls import path

from apps.notifications.consumers import PublicTournamentConsumer

websocket_urlpatterns = [
    path("ws/public/tournaments/<str:code>/", PublicTournamentConsumer.as_asgi()),
]
