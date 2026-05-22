import functools

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import ConflictError
from apps.tournaments.models import Tournament

from .models import ROUNDS_BY_DIMENSION, Bracket, Match
from .serializers import BracketGenerateSerializer, BracketSerializer


class TournamentScopedMixin:
    request: Request
    kwargs: dict

    @functools.cached_property
    def _tournament(self) -> Tournament:
        return get_object_or_404(
            Tournament, pk=self.kwargs["tournament_id"], owner=self.request.user
        )


def _generate_matches(bracket: Bracket, tournament: Tournament) -> Match:
    """Build the match tree bottom-up. Returns the root (finale) match."""
    rounds = ROUNDS_BY_DIMENSION[bracket.dimension]
    game_format = tournament.game_format

    current_round_matches: list[Match] = []

    for i, round_name in enumerate(rounds):
        num_matches = bracket.dimension // (2 ** (i + 1))

        if i == 0:
            new_matches = [
                Match.objects.create(
                    bracket=bracket,
                    round=round_name,
                    match_number=j + 1,
                    game_format=game_format,
                )
                for j in range(num_matches)
            ]
        else:
            prev = current_round_matches
            new_matches = []
            for j in range(num_matches):
                m = Match.objects.create(
                    bracket=bracket,
                    round=round_name,
                    match_number=j + 1,
                    game_format=game_format,
                    child1=prev[2 * j],
                    child2=prev[2 * j + 1],
                )
                new_matches.append(m)

        current_round_matches = new_matches

    return current_round_matches[0]


class BracketView(TournamentScopedMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: BracketSerializer},
        parameters=[
            OpenApiParameter(name="tournament_id", location=OpenApiParameter.PATH, type=int),
        ],
        summary="Récupérer le tableau principal",
    )
    def get(self, request: Request, tournament_id: int) -> Response:
        tournament = self._tournament
        bracket = get_object_or_404(Bracket, tournament=tournament)
        return Response(BracketSerializer(bracket).data)

    @extend_schema(
        request=BracketGenerateSerializer,
        responses={201: BracketSerializer},
        parameters=[
            OpenApiParameter(name="tournament_id", location=OpenApiParameter.PATH, type=int),
        ],
        summary="Générer le tableau principal",
        description=(
            "Génère l'arbre de matchs du tableau principal pour un tournoi. "
            "La dimension (N) définit le nombre de paires au départ (8, 16, 32 ou 64). "
            "Le nombre de têtes de série doit être compris entre N/8 et N/2. "
            "Retourne 409 si un tableau existe déjà pour ce tournoi."
        ),
    )
    def post(self, request: Request, tournament_id: int) -> Response:
        tournament = self._tournament

        if Bracket.objects.filter(tournament=tournament).exists():
            raise ConflictError(
                "Un tableau principal existe déjà pour ce tournoi."
            )

        serializer = BracketGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dimension: int = serializer.validated_data["dimension"]
        nb_top_seeds: int = serializer.validated_data["nb_top_seeds"]

        with transaction.atomic():
            bracket = Bracket.objects.create(
                tournament=tournament,
                dimension=dimension,
                nb_top_seeds=nb_top_seeds,
            )
            _generate_matches(bracket, tournament)

        return Response(BracketSerializer(bracket).data, status=status.HTTP_201_CREATED)
