from enum import StrEnum

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from apps.tournaments.models import Tournament


class Resource(StrEnum):
    TOURNAMENT = "tournament"
    MATCHES = "matches"
    BRACKET = "bracket"
    PAIRS = "pairs"


def group_name_for(public_code: str) -> str:
    return f"tournament_{public_code}"


def notify_public_update(tournament: Tournament, *resources: Resource) -> None:
    """Broadcast a real-time update to the public WebSocket group of
    `tournament`, once the current transaction commits.

    Diffusion is scheduled via `transaction.on_commit` because
    `ATOMIC_REQUESTS=True` wraps every request in a transaction —
    broadcasting before the commit would announce a change that could
    still be rolled back.
    """

    def _send() -> None:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            group_name_for(tournament.public_code),
            {"type": "tournament.update", "resources": [r.value for r in resources]},
        )

    transaction.on_commit(_send)
