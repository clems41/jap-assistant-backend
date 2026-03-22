from typing import Any

from django.db.models import TextChoices
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers
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


class _GameFormatDurationSerializer(Serializer):
    format = CharField()
    duration = serializers.IntegerField()


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


class TournamentGameFormatEnumView(APIView):
    """Return all valid tournament game format choices."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: _EnumChoiceSerializer(many=True)})
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return Response(enum_to_value_label(Tournament.GameFormat))


class TournamentConfigurationEnumView(APIView):
    """Return all valid tournament configuration choices."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: _EnumChoiceSerializer(many=True)})
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return Response(enum_to_value_label(Tournament.Configuration))


_TOURNAMENT_LIST_FILTERS = [
    OpenApiParameter(
        name="category",
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
        required=False,
        description="Filtrer par catégorie (ex: P100, P250).",
        enum=[c.value for c in Tournament.Category],
    ),
    OpenApiParameter(
        name="gender",
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
        required=False,
        description="Filtrer par genre (Homme, Femme, Mixte).",
        enum=[c.value for c in Tournament.Gender],
    ),
    OpenApiParameter(
        name="start_date",
        type=OpenApiTypes.DATE,
        location=OpenApiParameter.QUERY,
        required=False,
        description="Borne inférieure sur la date de début (inclusive, format ISO 8601).",
    ),
    OpenApiParameter(
        name="end_date",
        type=OpenApiTypes.DATE,
        location=OpenApiParameter.QUERY,
        required=False,
        description="Borne supérieure sur la date de début (inclusive, format ISO 8601).",
    ),
]


@extend_schema(parameters=_TOURNAMENT_LIST_FILTERS)
class TournamentListCreateView(generics.ListCreateAPIView):
    """List the authenticated user's tournaments or create a new one."""

    serializer_class = TournamentSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ["name", "start_date", "end_date", "created_at"]
    ordering = ["start_date"]

    def get_queryset(self):
        qs = Tournament.objects.filter(owner=self.request.user)

        category: str | None = self.request.query_params.get("category")
        if category is not None:
            qs = qs.filter(category=category)

        gender: str | None = self.request.query_params.get("gender")
        if gender is not None:
            qs = qs.filter(gender=gender)

        start_date: str | None = self.request.query_params.get("start_date")
        if start_date is not None:
            qs = qs.filter(start_date__gte=start_date)

        end_date: str | None = self.request.query_params.get("end_date")
        if end_date is not None:
            qs = qs.filter(start_date__lte=end_date)

        return qs

    def perform_create(self, serializer: BaseSerializer) -> None:
        serializer.save(owner=self.request.user)


class TournamentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a tournament owned by the authenticated user."""

    serializer_class = TournamentSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Tournament.objects.filter(owner=self.request.user)


class TournamentGameFormatDurationView(APIView):
    """Return the default estimated duration (in minutes) for each game format."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: _GameFormatDurationSerializer(many=True)})
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        data = [
            {"format": fmt, "duration": duration}
            for fmt, duration in Tournament.GAME_FORMAT_DEFAULT_DURATIONS.items()
        ]
        return Response(data)


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
