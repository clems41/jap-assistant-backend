import functools

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tournaments.models import Tournament

from .models import BracketSlot, BracketState
from .serializers import BracketStateSerializer, BracketStateWriteSerializer


class TournamentScopedMixin:
    request: Request
    kwargs: dict

    @functools.cached_property
    def _tournament(self) -> Tournament:
        return get_object_or_404(
            Tournament, pk=self.kwargs["tournament_id"], owner=self.request.user
        )


class BracketStateView(TournamentScopedMixin, APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: BracketStateSerializer},
        summary="Récupérer l'état du tableau",
        description=(
            "Retourne le bracket_state du tournoi avec toutes les paires placées dans les slots. "
            "Retourne 404 si aucun bracket n'a encore été sauvegardé pour ce tournoi."
        ),
    )
    def get(self, request: Request, tournament_id: int) -> Response:
        tournament = self._tournament
        bracket_state = get_object_or_404(BracketState, tournament=tournament)
        bracket_state_with_slots = (
            BracketState.objects.prefetch_related(
                "slots__pair__player1",
                "slots__pair__player2",
            )
            .get(pk=bracket_state.pk)
        )
        serializer = BracketStateSerializer(bracket_state_with_slots)
        return Response(serializer.data)

    @extend_schema(
        request=BracketStateWriteSerializer,
        responses={200: BracketStateSerializer},
        summary="Sauvegarder l'état du tableau",
        description=(
            "Crée ou écrase l'état du bracket pour ce tournoi. "
            "Tous les slots existants sont supprimés et remplacés par les nouveaux. "
            "Les slots vides ne doivent pas être envoyés."
        ),
    )
    def put(self, request: Request, tournament_id: int) -> Response:
        tournament = self._tournament
        serializer = BracketStateWriteSerializer(
            data=request.data,
            context={"tournament": tournament},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            bracket_state, created = BracketState.objects.update_or_create(
                tournament=tournament,
                defaults={
                    "dimension": data["dimension"],
                    "nb_top_seeds": data["nb_top_seeds"],
                },
            )
            BracketSlot.objects.filter(bracket_state=bracket_state).delete()
            BracketSlot.objects.bulk_create([
                BracketSlot(
                    bracket_state=bracket_state,
                    slot_title=slot["slot_title"],
                    pair_id=slot["pair_id"],
                    score=slot.get("score"),
                    game_format=slot.get("game_format"),
                )
                for slot in data["slots"]
            ])

        bracket_state_with_slots = (
            BracketState.objects.prefetch_related(
                "slots__pair__player1",
                "slots__pair__player2",
            )
            .get(pk=bracket_state.pk)
        )
        response_serializer = BracketStateSerializer(bracket_state_with_slots)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
