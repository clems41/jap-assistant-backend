from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.notifications.services import group_name_for
from apps.tournaments.models import Tournament


class PublicTournamentConsumer(AsyncJsonWebsocketConsumer):
    """Unidirectional push (server -> client) for the public, unauthenticated
    front-end of a tournament. Equivalent of the public REST views'
    `AllowAny` permission — no authentication is performed here.
    """

    group_name: str

    async def connect(self) -> None:
        code: str = self.scope["url_route"]["kwargs"]["code"]

        if not await self._tournament_exists(code):
            await self.close(code=4404)
            return

        self.group_name = group_name_for(code)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def tournament_update(self, event: dict[str, Any]) -> None:
        await self.send_json(event)

    @staticmethod
    @database_sync_to_async
    def _tournament_exists(code: str) -> bool:
        return Tournament.objects.filter(public_code=code).exists()
