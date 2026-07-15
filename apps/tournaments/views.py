import functools
from typing import Any

from django.db.models import TextChoices
from django.db.models.signals import post_delete, post_save
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer, CharField, Serializer
from rest_framework.views import APIView

from apps.common.exceptions import ConflictError
from apps.tournaments.models import TimeSlot, Tournament
from apps.tournaments.permissions import IsOwner
from apps.tournaments.serializers import (
    InformationsSerializer,
    PublicTournamentSerializer,
    TimeSlotSerializer,
    TournamentRecomputeStatusSerializer,
    TournamentSerializer,
    TournamentSetReadinessSerializer,
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
    OpenApiParameter(
        name="status",
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
        required=False,
        many=True,
        description="Filtrer par statut. Répétable : ?status=DRAFT&status=STARTED.",
        enum=[s.value for s in Tournament.Status],
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

        tournament_statuses: list[str] = self.request.query_params.getlist("status")
        if tournament_statuses:
            qs = qs.filter(status__in=tournament_statuses)

        return qs

    def perform_create(self, serializer: BaseSerializer) -> None:
        serializer.save(owner=self.request.user)


class TournamentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a tournament owned by the authenticated user."""

    serializer_class = TournamentSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Tournament.objects.filter(owner=self.request.user)

    def perform_update(self, serializer: BaseSerializer) -> None:
        if serializer.instance.is_locked:
            raise ConflictError("Ce tournoi ne peut plus être modifié.")
        serializer.save()

    def perform_destroy(self, instance: Tournament) -> None:
        if instance.is_locked:
            raise ConflictError("Ce tournoi ne peut plus être supprimé.")
        instance.delete()


class TournamentSetReadinessView(APIView):
    """Diagnostic breakdown of what's blocking a tournament from reaching Status.SET."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: TournamentSetReadinessSerializer},
        summary="Diagnostic des conditions manquantes pour passer au statut SET",
        description=(
            "Détaille chaque condition requise pour que le tournoi passe automatiquement "
            "au statut SET (configuration, format de jeu, nombre de paires, poids des paires, "
            "classement des joueurs). Utile pour diagnostiquer un tournoi bloqué en DRAFT."
        ),
    )
    def get(self, request: Request, pk: int) -> Response:
        tournament = _get_tournament_for_user(pk, request.user)
        serializer = TournamentSetReadinessSerializer(tournament.set_status_diagnostics())
        return Response(serializer.data)


class TournamentRecomputeStatusView(APIView):
    """Debug tool: force Tournament.recompute_status() directly, bypassing
    the save()/signal chain, and report the status before/after.

    Used to isolate whether recompute_status() itself works correctly versus
    whether the automatic post_save signal simply isn't firing for a given
    request path.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: TournamentRecomputeStatusSerializer},
        summary="Force le recalcul du statut d'un tournoi (outil de debug)",
        description=(
            "Appelle directement Tournament.recompute_status(), sans passer par "
            "une sauvegarde ni un signal. Retourne le statut avant et après "
            "l'appel. Outil de diagnostic — n'est normalement jamais nécessaire "
            "puisque le statut se recalcule automatiquement."
        ),
    )
    def post(self, request: Request, pk: int) -> Response:
        tournament = _get_tournament_for_user(pk, request.user)
        status_before = tournament.status
        tournament.recompute_status()
        tournament.refresh_from_db()
        serializer = TournamentRecomputeStatusSerializer(
            {"status_before": status_before, "status_after": tournament.status}
        )
        return Response(serializer.data)


class _SignalStatusSerializer(Serializer):
    tournament_post_save_count = serializers.IntegerField()
    pair_post_save_count = serializers.IntegerField()
    pair_post_delete_count = serializers.IntegerField()
    player_post_save_count = serializers.IntegerField()
    id_tournament = serializers.IntegerField()
    id_pair = serializers.IntegerField()
    id_player = serializers.IntegerField()
    raw_receivers = serializers.ListField(child=serializers.DictField())


def _raw_dispatch_uid_receivers(signal, expected_sender_id: int) -> list[dict]:
    """Inspect a Signal's internal receivers list for every entry registered
    with a "tournaments."-prefixed dispatch_uid, reporting the sender id it
    was actually connected against and whether that still matches the sender
    class currently in use by this process."""
    entries = []
    for receiver_entry in signal.receivers:
        lookup_key, receiver_ref = receiver_entry[0], receiver_entry[1]
        dispatch_uid = lookup_key[0]
        if not (isinstance(dispatch_uid, str) and dispatch_uid.startswith("tournaments.")):
            continue
        receiver = receiver_ref() if callable(receiver_ref) else receiver_ref
        entries.append(
            {
                "dispatch_uid": dispatch_uid,
                "sender_id": lookup_key[1],
                "sender_matches_current": lookup_key[1] == expected_sender_id,
                "alive": receiver is not None,
            }
        )
    return entries


class SignalStatusView(APIView):
    """Debug tool: report how many live post_save/post_delete receivers are
    registered for Tournament/Pair/Player in this process, plus a raw dump of
    each "tournaments."-dispatch_uid receiver's registered sender id compared
    against the sender class id currently seen by this process.

    Used to check whether apps.tournaments.signals.register_signals() (called
    from TournamentsConfig.ready()) actually ran — if tournament_post_save_count
    is 0, the automatic status recompute on save() is dead in this process. If
    counts are doubled with sender_matches_current=False entries, the receiver
    was connected against a stale/different Tournament class object.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: _SignalStatusSerializer})
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        from apps.players.models import Pair, Player

        raw_receivers = [
            *[
                {"signal": "post_save", **entry}
                for entry in _raw_dispatch_uid_receivers(post_save, id(Tournament))
                if entry["dispatch_uid"] == "tournaments.tournament_post_save"
            ],
            *[
                {"signal": "post_save", **entry}
                for entry in _raw_dispatch_uid_receivers(post_save, id(Pair))
                if entry["dispatch_uid"] == "tournaments.pair_post_save"
            ],
            *[
                {"signal": "post_delete", **entry}
                for entry in _raw_dispatch_uid_receivers(post_delete, id(Pair))
                if entry["dispatch_uid"] == "tournaments.pair_post_delete"
            ],
            *[
                {"signal": "post_save", **entry}
                for entry in _raw_dispatch_uid_receivers(post_save, id(Player))
                if entry["dispatch_uid"] == "tournaments.player_post_save"
            ],
        ]

        return Response(
            {
                "tournament_post_save_count": len(post_save._live_receivers(Tournament)),
                "pair_post_save_count": len(post_save._live_receivers(Pair)),
                "pair_post_delete_count": len(post_delete._live_receivers(Pair)),
                "player_post_save_count": len(post_save._live_receivers(Player)),
                "id_tournament": id(Tournament),
                "id_pair": id(Pair),
                "id_player": id(Player),
                "raw_receivers": raw_receivers,
            }
        )


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


class PublicTournamentScopedMixin:
    """Resolve the tournament from the public `code` URL kwarg.

    Shared by every public (unauthenticated) view scoped to a tournament —
    used both here and by apps.matches's public views.
    """

    request: Request
    kwargs: dict

    @functools.cached_property
    def _tournament(self) -> Tournament:
        return get_object_or_404(Tournament, public_code__iexact=self.kwargs["code"])


class PublicTournamentDetailView(generics.RetrieveAPIView):
    """Retrieve a tournament's public information by its public_code.

    Read-only, unauthenticated — intended for players without an account.
    """

    queryset = Tournament.objects.all()
    serializer_class = PublicTournamentSerializer
    permission_classes = [AllowAny]
    lookup_field = "public_code__iexact"
    lookup_url_kwarg = "code"
