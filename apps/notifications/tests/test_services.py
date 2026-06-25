import pytest
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from django.db import transaction

from apps.notifications.services import (
    Resource,
    group_name_for,
    notify_public_update,
)
from apps.tournaments.tests.factories import TournamentFactory


def test_group_name_for_builds_expected_group_name():
    assert group_name_for("ABC123") == "tournament_ABC123"


@pytest.mark.django_db
@pytest.mark.asyncio
async def test_notify_public_update_sends_resources_to_group(
    django_capture_on_commit_callbacks,
):
    tournament = await sync_to_async(TournamentFactory)()
    channel_layer = get_channel_layer()
    group_name = group_name_for(tournament.public_code)
    await channel_layer.group_add(group_name, "test-channel")

    def _notify_within_captured_commit() -> None:
        with django_capture_on_commit_callbacks(execute=True):
            notify_public_update(tournament, Resource.MATCHES, Resource.BRACKET)

    await sync_to_async(_notify_within_captured_commit)()

    message = await channel_layer.receive("test-channel")

    assert message["type"] == "tournament.update"
    assert message["resources"] == ["matches", "bracket"]


@pytest.mark.django_db(transaction=True)
def test_notify_public_update_does_not_send_without_commit():
    """transaction.on_commit callbacks never fire without an explicit
    commit — guards against notify_public_update broadcasting eagerly
    instead of deferring.

    Run synchronously (no event loop) with a real transaction
    (`transaction=True`) so `transaction.atomic()` below genuinely opens
    an atomic block on this test's own connection, mirroring
    `ATOMIC_REQUESTS=True` in production: the on_commit callback must be
    queued, not executed, while still inside that block.
    """
    tournament = TournamentFactory()

    with transaction.atomic():
        notify_public_update(tournament, Resource.TOURNAMENT)
        connection = transaction.get_connection()
        assert connection.run_on_commit, (
            "the callback must be queued on the connection, not executed "
            "immediately, while the atomic block is still open"
        )
