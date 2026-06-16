from typing import Any

from django.db.models import TextChoices
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer, CharField, Serializer
from rest_framework.views import APIView

from apps.tournaments.models import TimeSlot, Tournament
from apps.tournaments.permissions import IsOwner
from apps.tournaments.serializers import (
    InformationsSerializer,
    TimeSlotSerializer,
    TournamentSerializer,
)


def enum_to_value_label(choices_class: type[TextChoices]) -> list[dict[str, str]]:
    """Convert a TextChoices class into a list of {value, label} dicts."""
    return [{"value": member.value, "label": member.label} for member in choices_class]


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


class InformationsView(APIView):
    """Return pre-fill helper data: most recent league/location and all
    locations used by the authenticated user's tournaments, most
    recently used first."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: InformationsSerializer})
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        tournaments = list(
            Tournament.objects.filter(owner=request.user)
            .order_by("-created_at")
            .only("league", "location", "created_at")
        )

        last_league = tournaments[0].league if tournaments else None
        last_location = tournaments[0].location if tournaments else None

        seen: set[str] = set()
        all_locations: list[str] = []
        for tournament in tournaments:
            if tournament.location not in seen:
                seen.add(tournament.location)
                all_locations.append(tournament.location)

        return Response(
            {
                "last_league": last_league,
                "last_location": last_location,
                "all_locations": all_locations,
            }
        )


def _get_tournament_for_user(tournament_pk: int, user) -> Tournament:
    return get_object_or_404(Tournament, pk=tournament_pk, owner=user)


class TimeSlotListCreateView(generics.ListCreateAPIView):
    """List or create time slots for a tournament owned by the authenticated user."""

    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    ordering_fields = ["start_time", "end_time", "courts_available"]
    ordering = ["start_time"]

    def get_queryset(self):
        tournament = _get_tournament_for_user(
            self.kwargs["tournament_id"], self.request.user
        )
        return TimeSlot.objects.filter(tournament=tournament)

    def perform_create(self, serializer: BaseSerializer) -> None:
        tournament = _get_tournament_for_user(
            self.kwargs["tournament_id"], self.request.user
        )
        serializer.save(tournament=tournament)


class TimeSlotDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a time slot belonging to the authenticated user's tournament."""

    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tournament = _get_tournament_for_user(
            self.kwargs["tournament_id"], self.request.user
        )
        return TimeSlot.objects.filter(tournament=tournament)
