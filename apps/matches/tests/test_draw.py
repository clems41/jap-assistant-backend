"""Tests for the automatic bracket draw endpoint.

Setup used across most tests:
  dimension=16, nb_pair_round_8=4, nb_pair_round_16=8 (12 pairs total)
  TS1 (weight=1.0) → QUART #4 pair2
  TS2 (weight=2.0) → QUART #1 pair1
  Premier tour = HUITIEME_DE_FINALE
  10 remaining pairs to place: 2 at quart (other_slots), 8 at huitième

Active huitième matches (non-disabled) and their weight groups after draw:
  Demie1 subtree: H#2, H#4
    pair1 → high weight (9.0–12.0)
    pair2 → low weight  (5.0–8.0)
  Demie2 subtree: H#5, H#7
    pair2 → high weight (9.0–12.0)
    pair1 → low weight  (5.0–8.0)
"""

from unittest.mock import patch

import pytest

from apps.matches.models import Bracket, Match, Round
from apps.players.tests.factories import PairFactory
from apps.tournaments.tests.factories import TournamentFactory


def _draw_url(tournament_id: int) -> str:
    return f"/api/v1/tournaments/{tournament_id}/bracket/draw/"


def _bracket_url(tournament_id: int) -> str:
    return f"/api/v1/tournaments/{tournament_id}/bracket/"


_BRACKET_PAYLOAD_12 = {
    "dimension": 16,
    "nb_pair_round_64": 0,
    "nb_pair_round_32": 0,
    "nb_pair_round_16": 8,
    "nb_pair_round_8": 4,
    "nb_pair_round_4": 0,
}


@pytest.fixture
def tournament_12_pairs(user):
    """Tournament with 12 pairs: TS1(w=1.0), TS2(w=2.0), then w=3.0..12.0."""
    t = TournamentFactory(owner=user)
    ts1 = PairFactory(tournament=t, weight=1.0)
    ts2 = PairFactory(tournament=t, weight=2.0)
    others = [PairFactory(tournament=t, weight=float(w)) for w in range(3, 13)]
    return t, ts1, ts2, others


@pytest.mark.django_db
class TestBracketDraw:
    def _create_bracket(self, client, tournament_id: int, payload: dict | None = None) -> Bracket:
        if payload is None:
            payload = _BRACKET_PAYLOAD_12
        resp = client.post(_bracket_url(tournament_id), payload, format="json")
        assert resp.status_code == 201, resp.json()
        return Bracket.objects.get(tournament_id=tournament_id, parent__isnull=True)

    # ------------------------------------------------------------------ #
    # Error cases                                                          #
    # ------------------------------------------------------------------ #

    def test_404_if_no_bracket(self, authenticated_client, user):
        t = TournamentFactory(owner=user)
        resp = authenticated_client.post(_draw_url(t.pk))
        assert resp.status_code == 404

    def test_409_if_tournament_finished(self, authenticated_client, tournament_12_pairs):
        from apps.tournaments.models import Tournament

        t, *_ = tournament_12_pairs
        self._create_bracket(authenticated_client, t.pk)

        Tournament.objects.filter(pk=t.pk).update(status=Tournament.Status.FINISHED)

        resp = authenticated_client.post(_draw_url(t.pk))
        assert resp.status_code == 409

    def test_400_if_pair_missing_weight(self, authenticated_client, user):
        t = TournamentFactory(owner=user)
        PairFactory.create_batch(11, tournament=t, weight=100.0)
        PairFactory(tournament=t, weight=None)  # one pair without a weight

        self._create_bracket(authenticated_client, t.pk)

        resp = authenticated_client.post(_draw_url(t.pk))
        assert resp.status_code == 400
        assert "pairs" in resp.json().get("fields", {})

    # ------------------------------------------------------------------ #
    # Happy path — completeness and TS protection                         #
    # ------------------------------------------------------------------ #

    def test_all_pairs_placed_after_draw(self, authenticated_client, tournament_12_pairs):
        t, ts1, ts2, others = tournament_12_pairs
        self._create_bracket(authenticated_client, t.pk)

        resp = authenticated_client.post(_draw_url(t.pk))
        assert resp.status_code == 200

        bracket = Bracket.objects.get(tournament=t, parent__isnull=True)
        placed_ids: set[int] = set()
        for match in Match.objects.filter(bracket=bracket):
            if match.pair1_id:
                placed_ids.add(match.pair1_id)
            if match.pair2_id:
                placed_ids.add(match.pair2_id)

        all_pair_ids = set(t.pairs.values_list("id", flat=True))
        assert placed_ids == all_pair_ids

    def test_ts1_ts2_untouched_after_draw(self, authenticated_client, tournament_12_pairs):
        t, ts1, ts2, _ = tournament_12_pairs
        bracket = self._create_bracket(authenticated_client, t.pk)

        resp = authenticated_client.post(_draw_url(t.pk))
        assert resp.status_code == 200

        quart4 = Match.objects.get(bracket=bracket, round=Round.QUART_DE_FINALE, match_number=4)
        quart1 = Match.objects.get(bracket=bracket, round=Round.QUART_DE_FINALE, match_number=1)
        assert quart4.pair2_id == ts1.pk
        assert quart1.pair1_id == ts2.pk

    # ------------------------------------------------------------------ #
    # Weight grouping: other_slots (quart level)                          #
    # ------------------------------------------------------------------ #

    def test_non_premier_slots_get_strongest_pairs(self, authenticated_client, tournament_12_pairs):
        """The 2 quart-level other_slots receive the 2 pairs with lowest
        weight among unplaced pairs (weight=3.0 and weight=4.0), in any order."""
        t, *_ = tournament_12_pairs
        bracket = self._create_bracket(authenticated_client, t.pk)

        resp = authenticated_client.post(_draw_url(t.pk))
        assert resp.status_code == 200

        quart2 = Match.objects.select_related("pair1", "pair2").get(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=2
        )
        quart3 = Match.objects.select_related("pair1", "pair2").get(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=3
        )
        placed_weights = {quart2.pair1.weight, quart3.pair2.weight}
        assert placed_weights == {3.0, 4.0}

    # ------------------------------------------------------------------ #
    # Weight grouping: huitième slots                                     #
    # ------------------------------------------------------------------ #

    def test_low_weight_on_pair1_demie1_subtree(self, authenticated_client, tournament_12_pairs):
        """pair1 of active huitièmes in the demie1 subtree (H#2, H#4) get
        the stronger remaining pairs (weight <= 8.0)."""
        t, *_ = tournament_12_pairs
        bracket = self._create_bracket(authenticated_client, t.pk)

        resp = authenticated_client.post(_draw_url(t.pk))
        assert resp.status_code == 200

        for match_number in (2, 4):
            h = Match.objects.select_related("pair1").get(
                bracket=bracket, round=Round.HUITIEME_DE_FINALE, match_number=match_number
            )
            assert h.pair1.weight <= 8.0, (
                f"H#{match_number} pair1 weight={h.pair1.weight} should be <= 8.0 (low group)"
            )

    def test_low_weight_on_pair2_demie2_subtree(self, authenticated_client, tournament_12_pairs):
        """pair2 of active huitièmes in the demie2 subtree (H#5, H#7) get
        the stronger remaining pairs (weight <= 8.0)."""
        t, *_ = tournament_12_pairs
        bracket = self._create_bracket(authenticated_client, t.pk)

        resp = authenticated_client.post(_draw_url(t.pk))
        assert resp.status_code == 200

        for match_number in (5, 7):
            h = Match.objects.select_related("pair2").get(
                bracket=bracket, round=Round.HUITIEME_DE_FINALE, match_number=match_number
            )
            assert h.pair2.weight <= 8.0, (
                f"H#{match_number} pair2 weight={h.pair2.weight} should be <= 8.0 (low group)"
            )

    def test_high_weight_on_pair2_demie1_subtree(self, authenticated_client, tournament_12_pairs):
        """pair2 of active huitièmes in the demie1 subtree (H#2, H#4) get
        the weakest pairs (weight >= 9.0)."""
        t, *_ = tournament_12_pairs
        bracket = self._create_bracket(authenticated_client, t.pk)

        resp = authenticated_client.post(_draw_url(t.pk))
        assert resp.status_code == 200

        for match_number in (2, 4):
            h = Match.objects.select_related("pair2").get(
                bracket=bracket, round=Round.HUITIEME_DE_FINALE, match_number=match_number
            )
            assert h.pair2.weight >= 9.0, (
                f"H#{match_number} pair2 weight={h.pair2.weight} should be >= 9.0 (high group)"
            )

    def test_high_weight_on_pair1_demie2_subtree(self, authenticated_client, tournament_12_pairs):
        """pair1 of active huitièmes in the demie2 subtree (H#5, H#7) get
        the weakest pairs (weight >= 9.0)."""
        t, *_ = tournament_12_pairs
        bracket = self._create_bracket(authenticated_client, t.pk)

        resp = authenticated_client.post(_draw_url(t.pk))
        assert resp.status_code == 200

        for match_number in (5, 7):
            h = Match.objects.select_related("pair1").get(
                bracket=bracket, round=Round.HUITIEME_DE_FINALE, match_number=match_number
            )
            assert h.pair1.weight >= 9.0, (
                f"H#{match_number} pair1 weight={h.pair1.weight} should be >= 9.0 (high group)"
            )

    # ------------------------------------------------------------------ #
    # Randomness                                                          #
    # ------------------------------------------------------------------ #

    def test_placement_within_group_is_random(self, authenticated_client, tournament_12_pairs):
        """random.shuffle is called during the draw to randomize slot order."""
        t, *_ = tournament_12_pairs
        self._create_bracket(authenticated_client, t.pk)

        with patch("apps.matches.services.random.shuffle") as mock_shuffle:
            resp = authenticated_client.post(_draw_url(t.pk))
            assert resp.status_code == 200
            assert mock_shuffle.called

    # ------------------------------------------------------------------ #
    # Idempotency and existing placements                                 #
    # ------------------------------------------------------------------ #

    def test_idempotent_when_all_placed(self, authenticated_client, tournament_12_pairs):
        """Calling draw twice returns 200 both times; second call leaves
        all pair assignments unchanged."""
        t, *_ = tournament_12_pairs
        bracket = self._create_bracket(authenticated_client, t.pk)

        resp1 = authenticated_client.post(_draw_url(t.pk))
        assert resp1.status_code == 200

        snapshot_after_first = {
            m.pk: (m.pair1_id, m.pair2_id)
            for m in Match.objects.filter(bracket=bracket)
        }

        resp2 = authenticated_client.post(_draw_url(t.pk))
        assert resp2.status_code == 200

        snapshot_after_second = {
            m.pk: (m.pair1_id, m.pair2_id)
            for m in Match.objects.filter(bracket=bracket)
        }
        assert snapshot_after_first == snapshot_after_second

    def test_respects_existing_manual_placements(self, authenticated_client, tournament_12_pairs):
        """A pair manually placed before the draw is preserved by the draw."""
        t, ts1, ts2, others = tournament_12_pairs
        bracket = self._create_bracket(authenticated_client, t.pk)

        quart2 = Match.objects.get(bracket=bracket, round=Round.QUART_DE_FINALE, match_number=2)
        manually_placed = others[0]  # weight=3.0

        resp = authenticated_client.patch(
            f"/api/v1/tournaments/{t.pk}/bracket/placement/",
            {
                "placements": [
                    {
                        "match_id": quart2.pk,
                        "pair1_id": manually_placed.pk,
                        "pair2_id": None,
                    }
                ]
            },
            format="json",
        )
        assert resp.status_code == 200

        resp = authenticated_client.post(_draw_url(t.pk))
        assert resp.status_code == 200

        quart2.refresh_from_db()
        assert quart2.pair1_id == manually_placed.pk

    # ------------------------------------------------------------------ #
    # Multi-level other_slots: pairs assigned level by level              #
    # ------------------------------------------------------------------ #

    def test_multi_round_assigns_strongest_to_highest_level(
        self, authenticated_client, user
    ):
        """dimension=32, nb_pair_round_8=4, nb_pair_round_16=4, nb_pair_round_32=8
        (16 pairs total). After TS1/TS2 at quart, the 2 remaining quart slots
        must receive TS3 & TS4 (weight=3.0 and 4.0), the 4 active huitième
        slots must receive w=5.0-8.0, and the 8 seizième slots must receive
        w=9.0-16.0.
        """
        t = TournamentFactory(owner=user)
        PairFactory(tournament=t, weight=1.0)
        PairFactory(tournament=t, weight=2.0)
        for w in range(3, 17):
            PairFactory(tournament=t, weight=float(w))

        resp = authenticated_client.post(
            _bracket_url(t.pk),
            {
                "dimension": 32,
                "nb_pair_round_64": 0,
                "nb_pair_round_32": 8,
                "nb_pair_round_16": 4,
                "nb_pair_round_8": 4,
                "nb_pair_round_4": 0,
            },
            format="json",
        )
        assert resp.status_code == 201

        bracket = Bracket.objects.get(tournament=t, parent__isnull=True)

        resp = authenticated_client.post(_draw_url(t.pk))
        assert resp.status_code == 200

        # The 2 remaining quart slots must get the 2 strongest remaining pairs
        quart2 = Match.objects.select_related("pair1").get(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=2
        )
        quart3 = Match.objects.select_related("pair2").get(
            bracket=bracket, round=Round.QUART_DE_FINALE, match_number=3
        )
        placed_quart_weights = {quart2.pair1.weight, quart3.pair2.weight}
        assert placed_quart_weights == {3.0, 4.0}, (
            f"Quart slots should hold w=3.0 and 4.0, got {placed_quart_weights}"
        )

        # Active huitièmes (2, 4 in demie1; 5, 7 in demie2) hold w=5.0-8.0
        for match_number in (2, 4):
            h = Match.objects.select_related("pair1").get(
                bracket=bracket,
                round=Round.HUITIEME_DE_FINALE,
                match_number=match_number,
            )
            assert 5.0 <= h.pair1.weight <= 8.0, (
                f"H#{match_number} pair1 weight={h.pair1.weight} should be 5-8"
            )
        for match_number in (5, 7):
            h = Match.objects.select_related("pair2").get(
                bracket=bracket,
                round=Round.HUITIEME_DE_FINALE,
                match_number=match_number,
            )
            assert 5.0 <= h.pair2.weight <= 8.0, (
                f"H#{match_number} pair2 weight={h.pair2.weight} should be 5-8"
            )

    # ------------------------------------------------------------------ #
    # Edge case: all pairs enter in a single round                        #
    # ------------------------------------------------------------------ #

    def test_all_in_one_round(self, authenticated_client, user):
        """dimension=16, nb_pair_round_16=16: all 16 pairs enter at huitième.
        After the draw, every huitième match has both pair1 and pair2 set."""
        t = TournamentFactory(owner=user)
        PairFactory(tournament=t, weight=1.0)
        PairFactory(tournament=t, weight=2.0)
        PairFactory.create_batch(14, tournament=t, weight=100.0)

        resp = authenticated_client.post(
            _bracket_url(t.pk),
            {
                "dimension": 16,
                "nb_pair_round_64": 0,
                "nb_pair_round_32": 0,
                "nb_pair_round_16": 16,
                "nb_pair_round_8": 0,
                "nb_pair_round_4": 0,
            },
            format="json",
        )
        assert resp.status_code == 201

        bracket = Bracket.objects.get(tournament=t, parent__isnull=True)

        resp = authenticated_client.post(_draw_url(t.pk))
        assert resp.status_code == 200

        huitiemes = Match.objects.filter(bracket=bracket, round=Round.HUITIEME_DE_FINALE)
        for h in huitiemes:
            assert h.pair1_id is not None, f"H#{h.match_number} pair1 is still empty after draw"
            assert h.pair2_id is not None, f"H#{h.match_number} pair2 is still empty after draw"
