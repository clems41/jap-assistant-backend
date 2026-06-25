import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from apps.notifications.consumers import PublicTournamentConsumer
from apps.notifications.services import group_name_for
from apps.tournaments.tests.factories import TournamentFactory


def _communicator(code: str) -> WebsocketCommunicator:
    return WebsocketCommunicator(
        PublicTournamentConsumer.as_asgi(), f"/ws/public/tournaments/{code}/"
    )


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestPublicTournamentConsumerConnect:
    async def test_connect_with_valid_public_code_is_accepted(self):
        from asgiref.sync import sync_to_async

        tournament = await sync_to_async(TournamentFactory)()
        communicator = _communicator(tournament.public_code)
        communicator.scope["url_route"] = {"kwargs": {"code": tournament.public_code}}

        connected, _ = await communicator.connect()

        assert connected is True
        await communicator.disconnect()

    async def test_connect_with_unknown_code_is_closed_with_4404(self):
        communicator = _communicator("UNKNOWN1")
        communicator.scope["url_route"] = {"kwargs": {"code": "UNKNOWN1"}}

        connected, subprotocol_or_close_code = await communicator.connect()

        assert connected is False
        assert subprotocol_or_close_code == 4404


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestPublicTournamentConsumerBroadcast:
    async def test_group_send_is_relayed_to_connected_communicator(self):
        from asgiref.sync import sync_to_async

        tournament = await sync_to_async(TournamentFactory)()
        communicator = _communicator(tournament.public_code)
        communicator.scope["url_route"] = {"kwargs": {"code": tournament.public_code}}

        connected, _ = await communicator.connect()
        assert connected is True

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            group_name_for(tournament.public_code),
            {"type": "tournament.update", "resources": ["matches"]},
        )

        response = await communicator.receive_json_from()

        assert response == {"type": "tournament.update", "resources": ["matches"]}

        await communicator.disconnect()
