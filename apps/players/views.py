import csv
import functools
import io

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import ConflictError
from apps.tournaments.models import Tournament

from .models import Pair, Player
from .serializers import PairCSVImportSerializer, PairSerializer
from .services.ranking_matching_service import match_and_update_rankings

EXPECTED_HEADERS = [
    "last_name",
    "first_name",
    "license_number",
    "phone",
    "ranking",
    "last_name2",
    "first_name2",
    "license_number2",
    "phone2",
    "ranking2",
    "weight",
]

# French headers from the real FFT CSV export (no ranking columns)
EXPECTED_HEADERS_FR = [
    "Nom J1",
    "Prénom J1",
    "Licence J1",
    "Téléphone J1",
    "Nom J2",
    "Prénom J2",
    "Licence J2",
    "Téléphone J2",
]

# Mapping from French headers to internal field names
FRENCH_HEADER_MAP: dict[str, str] = {
    "Nom J1": "last_name",
    "Prénom J1": "first_name",
    "Licence J1": "license_number",
    "Téléphone J1": "phone",
    "Nom J2": "last_name2",
    "Prénom J2": "first_name2",
    "Licence J2": "license_number2",
    "Téléphone J2": "phone2",
}


class TournamentScopedMixin:
    request: Request
    kwargs: dict

    @functools.cached_property
    def _tournament(self) -> Tournament:
        return get_object_or_404(
            Tournament, pk=self.kwargs["tournament_id"], owner=self.request.user
        )


class PairListCreateView(TournamentScopedMixin, generics.ListCreateAPIView):
    serializer_class = PairSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    filter_backends = []

    def get_queryset(self):
        return Pair.objects.filter(tournament=self._tournament).select_related(
            "player1", "player2"
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["tournament"] = self._tournament
        return ctx

    def perform_create(self, serializer):
        if self._tournament.is_locked:
            raise ConflictError("Les paires ne peuvent plus être modifiées.")
        serializer.save(tournament=self._tournament)


class PairDetailView(TournamentScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PairSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Pair.objects.filter(tournament=self._tournament).select_related(
            "player1", "player2"
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["tournament"] = self._tournament
        return ctx

    def perform_update(self, serializer):
        if self._tournament.is_locked:
            raise ConflictError("Les paires ne peuvent plus être modifiées.")
        serializer.save()

    def perform_destroy(self, instance):
        if self._tournament.is_locked:
            raise ConflictError("Les paires ne peuvent plus être modifiées.")
        instance.delete()


class PairCSVImportView(TournamentScopedMixin, APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PairCSVImportSerializer,
        responses={201: PairSerializer(many=True)},
        parameters=[
            OpenApiParameter(
                name="tournament_id",
                location=OpenApiParameter.PATH,
                type=int,
            ),
        ],
        summary="Import des paires depuis un fichier CSV",
        description=(
            "Importe les paires d'un tournoi depuis un fichier CSV. "
            "Les paires existantes non présentes dans le CSV sont conservées. "
            "Si une paire avec les mêmes joueurs existe déjà, son poids est mis à jour. "
            "Les joueurs identifiés par leur numéro de licence sont créés ou mis à jour. "
            "Après l'import, un matching FFT est automatiquement déclenché pour les joueurs "
            "sans classement. "
            "La réponse contient l'ensemble des paires du tournoi (pas uniquement celles du CSV), "
            "avec les classements et poids mis à jour."
        ),
    )
    def post(self, request: Request, tournament_id: int) -> Response:
        tournament = self._tournament

        if tournament.is_locked:
            raise ConflictError("Les paires ne peuvent plus être modifiées.")

        file_serializer = PairCSVImportSerializer(data=request.data)
        file_serializer.is_valid(raise_exception=True)

        uploaded_file = file_serializer.validated_data["file"]
        content = uploaded_file.read().decode("utf-8")
        rows, error = self._parse_csv(content)
        if error:
            raise ValidationError({"file": [error]})

        self._create_pairs_from_csv(tournament, rows)
        pairs = match_and_update_rankings(tournament)
        output = PairSerializer(
            pairs,
            many=True,
            context={"request": request, "tournament": tournament},
        )
        return Response(output.data, status=status.HTTP_201_CREATED)

    def _parse_csv(self, content: str) -> tuple[list[dict], str | None]:
        reader = csv.DictReader(io.StringIO(content))
        headers = list(reader.fieldnames or [])

        if headers == EXPECTED_HEADERS:
            normalize = None
        elif headers == EXPECTED_HEADERS_FR:
            normalize = FRENCH_HEADER_MAP
        else:
            return [], f"En-têtes CSV invalides. Attendu : {', '.join(EXPECTED_HEADERS)}"

        rows = []
        seen_licenses: set[str] = set()

        for i, row in enumerate(reader, start=2):  # row 1 = headers
            if normalize is not None:
                row = {normalize.get(k, k): v for k, v in row.items()}

            for col in ["license_number", "license_number2"]:
                lic = row.get(col, "").strip()
                if not lic:
                    return [], f"Ligne {i} : le numéro de licence est obligatoire."
                if lic in seen_licenses:
                    return (
                        [],
                        f"Ligne {i} : le numéro de licence '{lic}' est en doublon dans le fichier.",
                    )
                seen_licenses.add(lic)
            rows.append(row)

        return rows, None

    @staticmethod
    def _build_player_defaults(row: dict, suffix: str = "") -> dict:
        """Build the defaults dict for update_or_create, omitting ranking when absent or empty."""
        defaults: dict = {
            "last_name": row[f"last_name{suffix}"].strip(),
            "first_name": row[f"first_name{suffix}"].strip(),
            "phone": row[f"phone{suffix}"].strip(),
        }
        ranking_raw = row.get(f"ranking{suffix}", "").strip()
        if ranking_raw:
            defaults["ranking"] = int(ranking_raw)
        return defaults

    def _create_pairs_from_csv(
        self, tournament: Tournament, rows: list[dict]
    ) -> list[Pair]:
        with transaction.atomic():
            pairs = []
            for row in rows:
                player1, _ = Player.objects.update_or_create(
                    license_number=row["license_number"].strip(),
                    defaults=self._build_player_defaults(row, suffix=""),
                )
                player2, _ = Player.objects.update_or_create(
                    license_number=row["license_number2"].strip(),
                    defaults=self._build_player_defaults(row, suffix="2"),
                )
                weight_str = row.get("weight", "").strip()
                weight = float(weight_str) if weight_str else None
                pair, created = Pair.objects.get_or_create(
                    tournament=tournament,
                    player1=player1,
                    player2=player2,
                    defaults={"weight": weight},
                )
                if not created and weight_str:
                    pair.weight = weight
                    pair.save(update_fields=["weight", "updated_at"])
                pairs.append(pair)
        return pairs


class RankingMatchingView(TournamentScopedMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: PairSerializer(many=True)},
        summary="Matching des classements FFT pour les paires du tournoi",
        description=(
            "Pour chaque joueur sans classement, cherche une correspondance dans la table FFTRanking "
            "par nom/prénom (filtré par genre du tournoi). "
            "Les classements existants ne sont pas modifiés. "
            "Recalcule le poids de la paire si les deux joueurs ont un classement."
        ),
        parameters=[
            OpenApiParameter(
                name="tournament_id",
                location=OpenApiParameter.PATH,
                type=int,
            ),
        ],
    )
    def get(self, request: Request, tournament_id: int) -> Response:
        if self._tournament.is_locked:
            raise ConflictError("Les paires ne peuvent plus être modifiées.")
        pairs = match_and_update_rankings(self._tournament)
        serializer = PairSerializer(
            pairs,
            many=True,
            context={"request": request, "tournament": self._tournament},
        )
        return Response(serializer.data)
