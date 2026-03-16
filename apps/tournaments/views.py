from typing import Any

from django.db.models import TextChoices
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer, CharField, Serializer
from rest_framework.views import APIView

from apps.tournaments.models import Tournament
from apps.tournaments.permissions import IsOwner
from apps.tournaments.serializers import LastLeagueSerializer, TournamentSerializer


def enum_to_value_label(choices_class: type[TextChoices]) -> list[dict[str, str]]:
    """Convert a TextChoices class into a list of {value, label} dicts."""
    return [
        {"value": member.value, "label": member.label}
        for member in choices_class
    ]


class _EnumChoiceSerializer(Serializer):
    value = CharField()
    label = CharField()


class TournamentCategoryEnumView(APIView):
    """Return all valid tournament category choices."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: _EnumChoiceSerializer(many=True)})
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return Response(enum_to_value_label(Tournament.Category))


class TournamentLeagueEnumView(APIView):
    """Return all valid tournament league choices."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: _EnumChoiceSerializer(many=True)})
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return Response(enum_to_value_label(Tournament.League))


class TournamentGenderEnumView(APIView):
    """Return all valid tournament gender choices."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: _EnumChoiceSerializer(many=True)})
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return Response(enum_to_value_label(Tournament.Gender))


class TournamentListCreateView(generics.ListCreateAPIView):
    """List the authenticated user's tournaments or create a new one."""

    serializer_class = TournamentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Tournament.objects.filter(owner=self.request.user)

    def perform_create(self, serializer: BaseSerializer) -> None:
        serializer.save(owner=self.request.user)


class TournamentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a tournament owned by the authenticated user."""

    serializer_class = TournamentSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Tournament.objects.filter(owner=self.request.user)


class LastLeagueView(APIView):
    """Return the league of the most recently created tournament by the authenticated user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: LastLeagueSerializer})
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        tournament = (
            Tournament.objects.filter(owner=request.user)
            .order_by("-created_at")
            .only("league")
            .first()
        )
        league = tournament.league if tournament is not None else None
        return Response({"league": league})
