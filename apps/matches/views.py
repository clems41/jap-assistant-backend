import functools

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import ConflictError
from apps.notifications.services import Resource, notify_public_update
from apps.players.models import Pair
from apps.tournaments.models import Tournament
from apps.tournaments.views import PublicTournamentScopedMixin

from .models import ROUNDS_BY_DIMENSION, Bracket, Match, Round
from .serializers import (
    BracketGenerateSerializer,
    BracketPlacementSerializer,
    BracketSerializer,
    MatchListSerializer,
    MatchOrderSerializer,
    MatchScoreSerializer,
    MatchSerializer,
    PublicBracketSerializer,
    PublicMatchListSerializer,
)
from .services import (
    assign_match_order,
    compute_estimated_start_times,
    draw_pairs,
    generate_classification_brackets,
    generate_match_tree,
    place_top_seeds,
)


class TournamentScopedMixin:
    request: Request
    kwargs: dict

    @functools.cached_property
    def _tournament(self) -> Tournament:
        return get_object_or_404(
            Tournament, pk=self.kwargs["tournament_id"], owner=self.request.user
        )


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
        bracket = get_object_or_404(Bracket, tournament=tournament, parent__isnull=True)
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

        if Bracket.objects.filter(tournament=tournament, parent__isnull=True).exists():
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
            generate_match_tree(bracket, tournament.game_format)
            place_top_seeds(bracket, tournament)
            bracket.recompute_placement_flags()
            generate_classification_brackets(bracket, tournament)
            assign_match_order(bracket)

        notify_public_update(tournament, Resource.MATCHES, Resource.BRACKET)

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

        bracket = get_object_or_404(Bracket, tournament=tournament, parent__isnull=True)
        was_started = tournament.status == Tournament.Status.STARTED
        bracket.delete()
        if was_started:
            tournament.revert_to_set()

        notify_public_update(
            tournament, Resource.MATCHES, Resource.BRACKET, Resource.TOURNAMENT
        )

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

        bracket = get_object_or_404(Bracket, tournament=tournament, parent__isnull=True)

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

        notify_public_update(tournament, Resource.MATCHES, Resource.BRACKET)

        return Response(BracketSerializer(bracket).data)


class BracketDrawView(TournamentScopedMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: BracketSerializer},
        parameters=[
            OpenApiParameter(
                name="tournament_id", location=OpenApiParameter.PATH, type=int
            ),
        ],
        summary="Tirage au sort automatique des paires",
        description=(
            "Effectue le tirage au sort des paires non encore placées dans le tableau "
            "principal. Les paires les plus fortes (poids le plus faible) sont placées "
            "dans les tours les plus avancés, les suivantes dans les huitièmes. "
            "Au premier tour, les paires les plus faibles sont placées du côté des têtes "
            "de série pour qu'elles s'affrontent dès le premier tour. "
            "L'opération est idempotente : si toutes les paires sont déjà placées, "
            "retourne 200 sans modification. "
            "Les placements manuels existants sont conservés. "
            "Retourne 404 si aucun tableau principal n'existe, 409 si le tournoi est "
            "terminé, 400 si une paire non placée n'a pas de poids renseigné."
        ),
    )
    def post(self, request: Request, tournament_id: int) -> Response:
        tournament = self._tournament

        if tournament.is_finished:
            raise ConflictError(
                "Le tirage ne peut pas être effectué : le tournoi est terminé."
            )

        bracket = get_object_or_404(Bracket, tournament=tournament, parent__isnull=True)

        draw_pairs(bracket, tournament)

        notify_public_update(tournament, Resource.MATCHES, Resource.BRACKET)

        return Response(BracketSerializer(bracket).data)


_MATCH_LIST_FILTERS = [
    OpenApiParameter(
        name="status",
        type=OpenApiTypes.STR,
        location=OpenApiParameter.QUERY,
        required=False,
        many=True,
        description=(
            "Filtrer par statut. Paramètre répétable pour filtrer sur "
            "plusieurs statuts à la fois (ex: ?status=UPCOMING&status=STARTED)."
        ),
        enum=[c.value for c in Match.Status],
    ),
]


@extend_schema(parameters=_MATCH_LIST_FILTERS)
class MatchListView(TournamentScopedMixin, generics.ListAPIView):
    serializer_class = MatchListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    ordering_fields = ["order"]
    ordering = ["order"]

    def get_queryset(self):
        qs = Match.objects.filter(
            bracket__tournament=self._tournament, disabled=False
        ).select_related("bracket")

        statuses = self.request.query_params.getlist("status")
        if statuses:
            qs = qs.filter(status__in=statuses)

        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # Always simulate over the full UPCOMING/STARTED/FINISHED set of the
        # tournament, regardless of the `?status=` filter applied to the
        # response, so the estimation stays consistent across requests.
        context["estimated_start_at_map"] = compute_estimated_start_times(
            self._tournament
        )
        return context


class MatchOrderView(TournamentScopedMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=MatchOrderSerializer,
        responses={200: MatchSerializer(many=True)},
        parameters=[
            OpenApiParameter(
                name="tournament_id", location=OpenApiParameter.PATH, type=int
            ),
        ],
        summary="Réordonner les matchs à venir",
        description=(
            "Persiste un nouvel ordre de passage pour les matchs UPCOMING du "
            "tournoi. La liste match_ids doit contenir exactement l'ensemble "
            "actuel des matchs UPCOMING et non désactivés du tournoi, chacun "
            "une seule fois : elle est rejetée en cas de doublon, d'ID "
            "inconnu ou appartenant à un autre tournoi, d'ID non-UPCOMING, "
            "d'ID désactivé, ou d'ID manquant. Les matchs désactivés "
            "(disabled=True, ex. byes/walkovers en cascade) sont exclus de "
            "l'ensemble réordonnable : ils ne sont ni requis ni acceptés "
            "dans la liste. Retourne le détail des matchs mis à jour, dans "
            "l'ordre de la requête."
        ),
    )
    def patch(self, request: Request, tournament_id: int) -> Response:
        tournament = self._tournament

        if tournament.is_finished:
            raise ConflictError(
                "L'ordre des matchs ne peut plus être modifié : le tournoi est terminé."
            )

        serializer = MatchOrderSerializer(
            data=request.data, context={"tournament": tournament}
        )
        serializer.is_valid(raise_exception=True)

        match_ids: list[int] = serializer.validated_data["match_ids"]
        matches_map: dict[int, Match] = serializer.validated_data["_matches"]

        updated: list[Match] = []
        for index, match_id in enumerate(match_ids):
            match = matches_map[match_id]
            match.order = index + 1
            updated.append(match)

        with transaction.atomic():
            Match.objects.bulk_update(updated, ["order"])

        notify_public_update(tournament, Resource.MATCHES)

        return Response(MatchSerializer(updated, many=True).data)


def _find_parent_slot(match: Match) -> tuple[Match, str] | None:
    """Return (parent_match, slot_name) where slot_name is "pair1" or
    "pair2" — the slot on the match `match` feeds into (the match this
    match's winner is/was propagated into) — or None if `match` is the
    FINALE (root, no parent).
    """
    parent_via_child1 = match.parent_as_child1.first()
    if parent_via_child1 is not None:
        return parent_via_child1, "pair1"

    parent_via_child2 = match.parent_as_child2.first()
    if parent_via_child2 is not None:
        return parent_via_child2, "pair2"

    return None


def _fill_slot(slot: tuple[Match, str] | None, pair: Pair | None) -> None:
    """Set `slot`'s target match field to `pair` (or None to clear it).
    Shared by winner/loser propagation and by their un-propagation in
    `MatchScoreView.delete()`.
    """
    if slot is None:
        return
    target, field_name = slot
    setattr(target, field_name, pair)
    target.save(update_fields=[field_name, "updated_at"])


def _propagate_winner(match: Match, winner: Pair) -> None:
    _fill_slot(_find_parent_slot(match), winner)


def _find_classification_slot(match: Match) -> tuple[Match, str] | None:
    """Return (target_match, slot_name) — the slot in the classification
    bracket fed by the losers of `match`'s round within `match`'s own
    bracket — or None if that bracket has no classification bracket for
    this round (e.g. the FINALE never has one).
    """
    bracket = match.bracket
    classification_bracket = bracket.children.filter(source_round=match.round).first()
    if classification_bracket is None:
        return None

    position = Match.objects.filter(
        bracket=bracket,
        round=match.round,
        disabled=False,
        match_number__lt=match.match_number,
    ).count()

    target_round = ROUNDS_BY_DIMENSION[classification_bracket.dimension][0]
    target_match_number = position // 2 + 1
    slot = "pair1" if position % 2 == 0 else "pair2"

    target_match = Match.objects.get(
        bracket=classification_bracket,
        round=target_round,
        match_number=target_match_number,
    )
    return target_match, slot


def _propagate_loser(match: Match, loser: Pair) -> None:
    _fill_slot(_find_classification_slot(match), loser)


def _guard_slot_has_no_winner(slot: tuple[Match, str] | None, message: str) -> None:
    """Raise ConflictError if `slot`'s target match already has a winner.
    Shared guard for both the parent slot and the classification slot
    checked by `MatchScoreView.delete()` before any mutation happens.
    """
    if slot is None:
        return
    target, _ = slot
    if target.winner_id is not None:
        raise ConflictError(message)


def _advance_tournament_status(match: Match, tournament: Tournament) -> None:
    tournament.mark_as_started()
    if match.round == Round.FINALE and match.bracket.parent_id is None:
        tournament.mark_as_finished()


class MatchStartView(TournamentScopedMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: MatchSerializer},
        parameters=[
            OpenApiParameter(
                name="tournament_id", location=OpenApiParameter.PATH, type=int
            ),
            OpenApiParameter(name="match_id", location=OpenApiParameter.PATH, type=int),
        ],
        summary="Lancer un match",
        description=(
            "Fait passer un match du statut UPCOMING à STARTED. "
            "Retourne 409 si le match a déjà été lancé ou est terminé, s'il est "
            "désactivé, si l'une des deux paires n'est pas encore définie, ou si "
            "le tournoi est terminé (sauf pour la finale)."
        ),
    )
    def post(self, request: Request, tournament_id: int, match_id: int) -> Response:
        tournament = self._tournament
        match = get_object_or_404(Match, pk=match_id, bracket__tournament=tournament)

        if tournament.is_finished and match.round != Round.FINALE:
            raise ConflictError(
                "Ce match ne peut plus être lancé : le tournoi est terminé."
            )

        if match.status != Match.Status.UPCOMING:
            raise ConflictError("Ce match a déjà été lancé ou est terminé.")

        if match.disabled:
            raise ConflictError("Ce match est désactivé et ne peut pas être lancé.")

        if match.pair1_id is None or match.pair2_id is None:
            raise ConflictError(
                "Les deux paires du match doivent être définies avant de "
                "pouvoir le lancer."
            )

        match.status = Match.Status.STARTED
        match.started_at = timezone.now()
        match.save(update_fields=["status", "started_at", "updated_at"])

        notify_public_update(tournament, Resource.MATCHES, Resource.BRACKET)

        return Response(MatchSerializer(match).data)


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
        match.status = Match.Status.FINISHED
        match.finished_at = timezone.now()
        match.save(
            update_fields=["score", "winner", "status", "finished_at", "updated_at"]
        )

        loser = match.pair2 if winner_id == match.pair1_id else match.pair1

        _propagate_winner(match, winner)
        _propagate_loser(match, loser)
        _advance_tournament_status(match, tournament)

        notify_public_update(
            tournament, Resource.MATCHES, Resource.BRACKET, Resource.TOURNAMENT
        )

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
            "Supprime le score et le vainqueur d'un match, et annule la propagation "
            "de ce vainqueur dans le match suivant (le slot pair1/pair2 concerné est "
            "remis à null). Le score d'un match ne peut être supprimé que si le match "
            "suivant n'a pas encore de vainqueur — retourne 409 sinon. La finale n'a "
            "pas de match suivant : son score peut donc toujours être supprimé, ce qui "
            "fait revenir le tournoi au statut STARTED. La suppression du score d'un "
            "autre match ne modifie pas le statut du tournoi."
        ),
    )
    def delete(self, request: Request, tournament_id: int, match_id: int) -> Response:
        tournament = self._tournament
        match = get_object_or_404(Match, pk=match_id, bracket__tournament=tournament)

        parent_slot = _find_parent_slot(match)
        _guard_slot_has_no_winner(
            parent_slot,
            "Le score de ce match ne peut pas être supprimé : "
            "le match suivant a déjà un vainqueur.",
        )

        classification_slot = _find_classification_slot(match)
        _guard_slot_has_no_winner(
            classification_slot,
            "Le score de ce match ne peut pas être supprimé : le "
            "match de classement correspondant a déjà un vainqueur.",
        )

        match.score = ""
        match.winner = None
        match.status = Match.Status.UPCOMING
        match.started_at = None
        match.finished_at = None
        match.save(
            update_fields=[
                "score",
                "winner",
                "status",
                "started_at",
                "finished_at",
                "updated_at",
            ]
        )

        _fill_slot(parent_slot, None)
        _fill_slot(classification_slot, None)

        if match.round == Round.FINALE and match.bracket.parent_id is None:
            tournament.revert_to_started()

        notify_public_update(
            tournament, Resource.MATCHES, Resource.BRACKET, Resource.TOURNAMENT
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(parameters=_MATCH_LIST_FILTERS)
class PublicMatchListView(PublicTournamentScopedMixin, generics.ListAPIView):
    """List a tournament's matches by its public_code. Read-only,
    unauthenticated — intended for players without an account."""

    serializer_class = PublicMatchListSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    ordering_fields = ["order"]
    ordering = ["order"]

    def get_queryset(self):
        qs = Match.objects.filter(
            bracket__tournament=self._tournament, disabled=False
        ).select_related(
            "bracket",
            "pair1__player1",
            "pair1__player2",
            "pair2__player1",
            "pair2__player2",
            "winner__player1",
            "winner__player2",
        )

        statuses = self.request.query_params.getlist("status")
        if statuses:
            qs = qs.filter(status__in=statuses)

        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["estimated_start_at_map"] = compute_estimated_start_times(
            self._tournament
        )
        return context


class PublicBracketView(PublicTournamentScopedMixin, APIView):
    """Retrieve the main bracket (and its classification brackets) by the
    tournament's public_code. Read-only, unauthenticated."""

    permission_classes = [AllowAny]

    @extend_schema(
        responses={200: PublicBracketSerializer},
        parameters=[
            OpenApiParameter(name="code", location=OpenApiParameter.PATH, type=str),
        ],
        summary="Récupérer le tableau principal (accès public)",
    )
    def get(self, request: Request, code: str) -> Response:
        tournament = self._tournament
        bracket = get_object_or_404(Bracket, tournament=tournament, parent__isnull=True)
        return Response(PublicBracketSerializer(bracket).data)
