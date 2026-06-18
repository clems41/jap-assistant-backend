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
from apps.players.models import Pair
from apps.tournaments.models import Tournament

from .models import ROUNDS_BY_DIMENSION, Bracket, Match, Round
from .serializers import (
    BracketGenerateSerializer,
    BracketPlacementSerializer,
    BracketSerializer,
    MatchScoreSerializer,
    MatchSerializer,
)


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
            OpenApiParameter(
                name="tournament_id", location=OpenApiParameter.PATH, type=int
            ),
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
            OpenApiParameter(
                name="tournament_id", location=OpenApiParameter.PATH, type=int
            ),
        ],
        summary="Générer le tableau principal",
        description=(
            "Génère l'arbre de matchs du tableau principal pour un tournoi. "
            "La dimension (N) définit le nombre de paires au départ (8, 16, 32 ou 64). "
            "Pour chaque tour (nb_pair_round_64, nb_pair_round_32, nb_pair_round_16, "
            "nb_pair_round_8, nb_pair_round_4), indique combien de paires entrent "
            "directement dans ce tour sans avoir joué les tours précédents. "
            "La somme des 5 champs doit être égale au nombre de paires inscrites "
            "au tournoi, et un champ dont le tour est plus grand que la dimension "
            "doit être à 0. "
            "Retourne 409 si un tableau existe déjà pour ce tournoi."
        ),
    )
    def post(self, request: Request, tournament_id: int) -> Response:
        tournament = self._tournament

        if Bracket.objects.filter(tournament=tournament).exists():
            raise ConflictError("Un tableau principal existe déjà pour ce tournoi.")

        serializer = BracketGenerateSerializer(
            data=request.data, context={"tournament": tournament}
        )
        serializer.is_valid(raise_exception=True)

        dimension: int = serializer.validated_data["dimension"]

        with transaction.atomic():
            bracket = Bracket.objects.create(
                tournament=tournament,
                dimension=dimension,
                nb_pair_round_64=serializer.validated_data["nb_pair_round_64"],
                nb_pair_round_32=serializer.validated_data["nb_pair_round_32"],
                nb_pair_round_16=serializer.validated_data["nb_pair_round_16"],
                nb_pair_round_8=serializer.validated_data["nb_pair_round_8"],
                nb_pair_round_4=serializer.validated_data["nb_pair_round_4"],
            )
            _generate_matches(bracket, tournament)

        return Response(BracketSerializer(bracket).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        responses={204: None},
        parameters=[
            OpenApiParameter(
                name="tournament_id", location=OpenApiParameter.PATH, type=int
            ),
        ],
        summary="Supprimer le tableau principal",
        description=(
            "Supprime le tableau principal et tous les matchs associés. "
            "Après suppression, un nouveau tableau peut être généré avec une dimension différente."
        ),
    )
    def delete(self, request: Request, tournament_id: int) -> Response:
        tournament = self._tournament

        if tournament.is_finished:
            raise ConflictError(
                "Le tableau ne peut pas être supprimé : le tournoi est terminé."
            )

        bracket = get_object_or_404(Bracket, tournament=tournament)
        was_started = tournament.status == Tournament.Status.STARTED
        bracket.delete()
        if was_started:
            tournament.revert_to_set()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BracketPlacementView(TournamentScopedMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=BracketPlacementSerializer,
        responses={200: BracketSerializer},
        parameters=[
            OpenApiParameter(
                name="tournament_id", location=OpenApiParameter.PATH, type=int
            ),
        ],
        summary="Sauvegarder le placement des paires",
        description=(
            "Met à jour les paires dans les matchs du tableau. "
            "Les paires ordinaires vont dans les matchs du 1er tour ; "
            "les têtes de série peuvent être placées directement dans les tours suivants. "
            "Seuls les matchs inclus dans la requête sont modifiés. "
            "pair1_id / pair2_id peuvent être null pour dé-placer une paire."
        ),
    )
    def patch(self, request: Request, tournament_id: int) -> Response:
        tournament = self._tournament

        if tournament.is_finished:
            raise ConflictError(
                "Le placement ne peut plus être modifié : le tournoi est terminé."
            )

        bracket = get_object_or_404(Bracket, tournament=tournament)

        serializer = BracketPlacementSerializer(
            data=request.data,
            context={"bracket": bracket, "tournament": tournament},
        )
        serializer.is_valid(raise_exception=True)

        matches_map: dict = serializer.validated_data["_matches"]
        with transaction.atomic():
            for p in serializer.validated_data["placements"]:
                match = matches_map[p["match_id"]]
                match.pair1_id = p["pair1_id"]
                match.pair2_id = p["pair2_id"]
                match.save(update_fields=["pair1", "pair2", "updated_at"])

            bracket.recompute_placement_flags()

        return Response(BracketSerializer(bracket).data)


def _propagate_winner(match: Match, winner: Pair) -> None:
    parent_via_child1 = match.parent_as_child1.first()
    if parent_via_child1 is not None:
        parent_via_child1.pair1 = winner
        parent_via_child1.save(update_fields=["pair1", "updated_at"])
        return

    parent_via_child2 = match.parent_as_child2.first()
    if parent_via_child2 is not None:
        parent_via_child2.pair2 = winner
        parent_via_child2.save(update_fields=["pair2", "updated_at"])


def _advance_tournament_status(match: Match, tournament: Tournament) -> None:
    tournament.mark_as_started()
    if match.round == Round.FINALE:
        tournament.mark_as_finished()


class MatchScoreView(TournamentScopedMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=MatchScoreSerializer,
        responses={200: MatchSerializer},
        parameters=[
            OpenApiParameter(
                name="tournament_id", location=OpenApiParameter.PATH, type=int
            ),
            OpenApiParameter(name="match_id", location=OpenApiParameter.PATH, type=int),
        ],
        summary="Saisir le score d'un match",
        description=(
            "Met à jour le score et le vainqueur d'un match. "
            "Propage automatiquement le vainqueur au match parent si applicable."
        ),
    )
    def patch(self, request: Request, tournament_id: int, match_id: int) -> Response:
        tournament = self._tournament
        match = get_object_or_404(Match, pk=match_id, bracket__tournament=tournament)

        if tournament.is_finished and match.round != Round.FINALE:
            raise ConflictError(
                "Ce score ne peut plus être modifié : le tournoi est terminé."
            )

        serializer = MatchScoreSerializer(data=request.data, context={"match": match})
        serializer.is_valid(raise_exception=True)

        winner_id: int = serializer.validated_data["winner_id"]
        score: str = serializer.validated_data["score"]

        winner = Pair.objects.get(pk=winner_id)
        match.score = score
        match.winner = winner
        match.save(update_fields=["score", "winner", "updated_at"])

        _propagate_winner(match, winner)
        _advance_tournament_status(match, tournament)

        return Response(MatchSerializer(match).data)

    @extend_schema(
        responses={204: None},
        parameters=[
            OpenApiParameter(
                name="tournament_id", location=OpenApiParameter.PATH, type=int
            ),
            OpenApiParameter(name="match_id", location=OpenApiParameter.PATH, type=int),
        ],
        summary="Supprimer le score d'un match",
        description=(
            "Supprime le score et le vainqueur d'un match. "
            "Réservé à la correction du score de la finale une fois le tournoi terminé : "
            "cette opération fait revenir le tournoi au statut STARTED."
        ),
    )
    def delete(self, request: Request, tournament_id: int, match_id: int) -> Response:
        tournament = self._tournament
        match = get_object_or_404(Match, pk=match_id, bracket__tournament=tournament)

        if not (tournament.is_finished and match.round == Round.FINALE):
            raise ConflictError("Le score de ce match ne peut pas être supprimé.")

        match.score = ""
        match.winner = None
        match.save(update_fields=["score", "winner", "updated_at"])
        tournament.revert_to_started()

        return Response(status=status.HTTP_204_NO_CONTENT)
