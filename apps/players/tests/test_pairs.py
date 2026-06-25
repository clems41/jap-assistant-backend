"""
Tests for automatic weight calculation on Pair create/update.

Business rule:
  weight = player1.ranking + player2.ranking

The calculation must trigger automatically when rankings are provided.
If either ranking is missing (None), weight stays unchanged.
"""

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.notifications.services import Resource
from apps.players.tests.factories import PairFactory, PlayerFactory
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory

PAIRS_URL = "/api/v1/tournaments/{tournament_id}/pairs/"
PAIR_DETAIL_URL = "/api/v1/tournaments/{tournament_id}/pairs/{pk}/"


def pairs_url(tournament_id: int) -> str:
    return PAIRS_URL.format(tournament_id=tournament_id)


def pair_detail_url(tournament_id: int, pk: int) -> str:
    return PAIR_DETAIL_URL.format(tournament_id=tournament_id, pk=pk)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def tournament(user):
    return TournamentFactory(owner=user)


# ---------------------------------------------------------------------------
# TestPairWeightCalculationOnCreate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPairWeightCalculationOnCreate:
    def test_create_pair_weight_auto_calculated_from_rankings(
        self, auth_client, tournament
    ):
        """When both players have rankings, weight = ranking1 + ranking2 on create."""
        payload = {
            "player1": {
                "last_name": "Martin",
                "first_name": "Julien",
                "license_number": "WC_CREATE001",
                "phone": "",
                "ranking": 300,
            },
            "player2": {
                "last_name": "Roux",
                "first_name": "Quentin",
                "license_number": "WC_CREATE002",
                "phone": "",
                "ranking": 200,
            },
        }
        response = auth_client.post(pairs_url(tournament.id), data=payload, format="json")
        assert response.status_code == 201
        assert response.data["weight"] == 500.0

    def test_create_pair_weight_not_calculated_when_player1_ranking_missing(
        self, auth_client, tournament
    ):
        """When player1 has no ranking, weight stays None (no calculation)."""
        payload = {
            "player1": {
                "last_name": "Martin",
                "first_name": "Julien",
                "license_number": "WC_CREATE003",
                "phone": "",
                "ranking": None,
            },
            "player2": {
                "last_name": "Roux",
                "first_name": "Quentin",
                "license_number": "WC_CREATE004",
                "phone": "",
                "ranking": 200,
            },
        }
        response = auth_client.post(pairs_url(tournament.id), data=payload, format="json")
        assert response.status_code == 201
        assert response.data["weight"] is None

    def test_create_pair_weight_not_calculated_when_player2_ranking_missing(
        self, auth_client, tournament
    ):
        """When player2 has no ranking, weight stays None (no calculation)."""
        payload = {
            "player1": {
                "last_name": "Martin",
                "first_name": "Julien",
                "license_number": "WC_CREATE005",
                "phone": "",
                "ranking": 300,
            },
            "player2": {
                "last_name": "Roux",
                "first_name": "Quentin",
                "license_number": "WC_CREATE006",
                "phone": "",
                "ranking": None,
            },
        }
        response = auth_client.post(pairs_url(tournament.id), data=payload, format="json")
        assert response.status_code == 201
        assert response.data["weight"] is None

    def test_create_pair_explicit_weight_overridden_by_rankings(
        self, auth_client, tournament
    ):
        """When both rankings are provided, they override any explicit weight value."""
        payload = {
            "player1": {
                "last_name": "Martin",
                "first_name": "Julien",
                "license_number": "WC_CREATE007",
                "phone": "",
                "ranking": 400,
            },
            "player2": {
                "last_name": "Roux",
                "first_name": "Quentin",
                "license_number": "WC_CREATE008",
                "phone": "",
                "ranking": 100,
            },
            "weight": 999.9,
        }
        response = auth_client.post(pairs_url(tournament.id), data=payload, format="json")
        assert response.status_code == 201
        assert response.data["weight"] == 500.0


# ---------------------------------------------------------------------------
# TestPairWeightCalculationOnUpdate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPairWeightCalculationOnUpdate:
    def test_patch_with_rankings_recalculates_weight(self, auth_client, tournament):
        """PATCH with rankings for both players recalculates weight automatically."""
        pair = PairFactory(tournament=tournament, weight=100.0)
        payload = {
            "player1": {
                "last_name": pair.player1.last_name,
                "first_name": pair.player1.first_name,
                "license_number": pair.player1.license_number,
                "phone": pair.player1.phone,
                "ranking": 350,
            },
            "player2": {
                "last_name": pair.player2.last_name,
                "first_name": pair.player2.first_name,
                "license_number": pair.player2.license_number,
                "phone": pair.player2.phone,
                "ranking": 150,
            },
        }
        response = auth_client.patch(
            pair_detail_url(tournament.id, pair.id), data=payload, format="json"
        )
        assert response.status_code == 200
        assert response.data["weight"] == 500.0

    def test_patch_only_weight_does_not_trigger_recalculation(
        self, auth_client, tournament
    ):
        """PATCH with only weight (no player rankings) keeps the provided weight."""
        pair = PairFactory(tournament=tournament, weight=100.0)
        response = auth_client.patch(
            pair_detail_url(tournament.id, pair.id),
            data={"weight": 750.0},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["weight"] == 750.0

    def test_patch_with_only_player1_ranking_does_not_recalculate(
        self, auth_client, tournament
    ):
        """PATCH providing ranking only for player1 does not recalculate weight."""
        player2 = PlayerFactory(ranking=None)
        pair = PairFactory(tournament=tournament, player2=player2, weight=100.0)
        payload = {
            "player1": {
                "last_name": pair.player1.last_name,
                "first_name": pair.player1.first_name,
                "license_number": pair.player1.license_number,
                "phone": pair.player1.phone,
                "ranking": 400,
            },
        }
        response = auth_client.patch(
            pair_detail_url(tournament.id, pair.id), data=payload, format="json"
        )
        assert response.status_code == 200
        # player2 has no ranking, so no auto-calc — weight should be unchanged
        assert response.data["weight"] == 100.0

    def test_put_with_rankings_recalculates_weight(self, auth_client, tournament):
        """PUT with rankings for both players recalculates weight automatically."""
        pair = PairFactory(tournament=tournament, weight=100.0)
        payload = {
            "player1": {
                "last_name": "Alpha",
                "first_name": "Un",
                "license_number": "WC_PUT001",
                "phone": "",
                "ranking": 600,
            },
            "player2": {
                "last_name": "Beta",
                "first_name": "Deux",
                "license_number": "WC_PUT002",
                "phone": "",
                "ranking": 400,
            },
        }
        response = auth_client.put(
            pair_detail_url(tournament.id, pair.id), data=payload, format="json"
        )
        assert response.status_code == 200
        assert response.data["weight"] == 1000.0

    def test_patch_updates_player_ranking_in_db(self, auth_client, tournament):
        """PATCH with a new ranking actually persists the player ranking to the DB."""
        pair = PairFactory(tournament=tournament)
        pair.player1.ranking = 100
        pair.player1.save()
        pair.player2.ranking = 200
        pair.player2.save()

        payload = {
            "player1": {
                "last_name": pair.player1.last_name,
                "first_name": pair.player1.first_name,
                "license_number": pair.player1.license_number,
                "phone": pair.player1.phone,
                "ranking": 450,
            },
            "player2": {
                "last_name": pair.player2.last_name,
                "first_name": pair.player2.first_name,
                "license_number": pair.player2.license_number,
                "phone": pair.player2.phone,
                "ranking": 550,
            },
        }
        response = auth_client.patch(
            pair_detail_url(tournament.id, pair.id), data=payload, format="json"
        )
        assert response.status_code == 200
        assert response.data["weight"] == 1000.0

        pair.player1.refresh_from_db()
        pair.player2.refresh_from_db()
        assert pair.player1.ranking == 450
        assert pair.player2.ranking == 550


# ---------------------------------------------------------------------------
# TestPairRankingUpdateBehavior
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPairRankingUpdateBehavior:
    """Tests verifying that explicit rankings in PATCH/PUT are never overwritten by FFT.

    Business rules:
    - Ranking explicitly provided in the request → keep as-is, no FFT re-fetch.
    - Name changed without explicit ranking → re-fetch FFT (force=True).
    - Other fields only (phone, etc.) → keep existing ranking (force=False).
    """

    def test_patch_explicit_ranking_player1_not_overwritten_by_fft(
        self, auth_client, tournament, monkeypatch
    ):
        """PATCH with only player1 ranking → ranking saved as-is, FFT not called force=True."""
        calls = []

        def fake_fill(players, tournament, force=False):
            calls.append({"players": list(players), "force": force})

        monkeypatch.setattr(
            "apps.players.serializers.fill_rankings_for_players", fake_fill
        )

        pair = PairFactory(tournament=tournament)
        pair.player1.ranking = 100
        pair.player1.save()
        p1_pk = pair.player1.pk

        payload = {
            "player1": {
                "last_name": pair.player1.last_name,
                "first_name": pair.player1.first_name,
                "license_number": pair.player1.license_number,
                "phone": pair.player1.phone,
                "ranking": 999,
            },
        }
        response = auth_client.patch(
            pair_detail_url(tournament.id, pair.id), data=payload, format="json"
        )
        assert response.status_code == 200

        pair.player1.refresh_from_db()
        assert pair.player1.ranking == 999

        # FFT must not have been called with force=True for player1
        for call in calls:
            if call["force"]:
                pks = {p.pk for p in call["players"]}
                assert p1_pk not in pks, (
                    "fill_rankings_for_players called with force=True for player1 "
                    "even though ranking was explicitly provided"
                )

    def test_patch_explicit_ranking_player2_not_overwritten_by_fft(
        self, auth_client, tournament, monkeypatch
    ):
        """PATCH with only player2 ranking → ranking saved as-is, FFT not called force=True."""
        calls = []

        def fake_fill(players, tournament, force=False):
            calls.append({"players": list(players), "force": force})

        monkeypatch.setattr(
            "apps.players.serializers.fill_rankings_for_players", fake_fill
        )

        pair = PairFactory(tournament=tournament)
        pair.player2.ranking = 200
        pair.player2.save()
        p2_pk = pair.player2.pk

        payload = {
            "player2": {
                "last_name": pair.player2.last_name,
                "first_name": pair.player2.first_name,
                "license_number": pair.player2.license_number,
                "phone": pair.player2.phone,
                "ranking": 888,
            },
        }
        response = auth_client.patch(
            pair_detail_url(tournament.id, pair.id), data=payload, format="json"
        )
        assert response.status_code == 200

        pair.player2.refresh_from_db()
        assert pair.player2.ranking == 888

        for call in calls:
            if call["force"]:
                pks = {p.pk for p in call["players"]}
                assert p2_pk not in pks, (
                    "fill_rankings_for_players called with force=True for player2 "
                    "even though ranking was explicitly provided"
                )

    def test_patch_name_changed_without_ranking_triggers_fft_force(
        self, auth_client, tournament, monkeypatch
    ):
        """PATCH with changed last_name but no explicit ranking → FFT called force=True."""
        calls = []

        def fake_fill(players, tournament, force=False):
            calls.append({"players": list(players), "force": force})

        monkeypatch.setattr(
            "apps.players.serializers.fill_rankings_for_players", fake_fill
        )

        pair = PairFactory(tournament=tournament)
        pair.player1.ranking = 300
        pair.player1.save()
        p1_pk = pair.player1.pk

        payload = {
            "player1": {
                "last_name": "NouveauNom",
                "first_name": pair.player1.first_name,
                "license_number": pair.player1.license_number,
                "phone": pair.player1.phone,
                # no "ranking" key → not explicitly provided
            },
        }
        response = auth_client.patch(
            pair_detail_url(tournament.id, pair.id), data=payload, format="json"
        )
        assert response.status_code == 200

        # FFT must have been called with force=True for player1
        force_true_calls = [c for c in calls if c["force"] is True]
        assert force_true_calls, (
            "fill_rankings_for_players was never called with force=True "
            "despite player1 last_name being changed"
        )
        force_pks = {p.pk for p in force_true_calls[0]["players"]}
        assert p1_pk in force_pks

    def test_patch_name_changed_with_explicit_ranking_keeps_manual_ranking(
        self, auth_client, tournament, monkeypatch
    ):
        """PATCH with changed name AND explicit ranking → manual ranking kept, FFT skipped."""
        calls = []

        def fake_fill(players, tournament, force=False):
            calls.append({"players": list(players), "force": force})

        monkeypatch.setattr(
            "apps.players.serializers.fill_rankings_for_players", fake_fill
        )

        pair = PairFactory(tournament=tournament)
        pair.player1.ranking = 300
        pair.player1.save()
        p1_pk = pair.player1.pk

        payload = {
            "player1": {
                "last_name": "NomModifie",
                "first_name": pair.player1.first_name,
                "license_number": pair.player1.license_number,
                "phone": pair.player1.phone,
                "ranking": 777,
            },
        }
        response = auth_client.patch(
            pair_detail_url(tournament.id, pair.id), data=payload, format="json"
        )
        assert response.status_code == 200

        pair.player1.refresh_from_db()
        assert pair.player1.ranking == 777

        for call in calls:
            if call["force"]:
                pks = {p.pk for p in call["players"]}
                assert p1_pk not in pks, (
                    "fill_rankings_for_players called with force=True for player1 "
                    "even though ranking was explicitly provided"
                )

    def test_put_name_changed_ranking_same_value_triggers_fft_force(
        self, auth_client, tournament, monkeypatch
    ):
        """PUT with name changed + ranking sent but same value as DB → FFT called force=True.

        This is the bug case: with PUT all fields are always in the payload.
        'ranking' being present does not mean it was intentionally changed.
        Only a ranking value that DIFFERS from the current DB value is considered explicit.
        """
        calls = []

        def fake_fill(players, tournament, force=False):
            calls.append({"players": list(players), "force": force})

        monkeypatch.setattr(
            "apps.players.serializers.fill_rankings_for_players", fake_fill
        )

        pair = PairFactory(tournament=tournament)
        pair.player1.ranking = 300
        pair.player1.save()
        p1_pk = pair.player1.pk

        # PUT with the same ranking value (300) but a changed name.
        # The ranking should NOT be treated as explicit because value == DB value.
        # FFT must be called with force=True because the name changed.
        payload = {
            "player1": {
                "last_name": "NomDifferent",
                "first_name": pair.player1.first_name,
                "license_number": pair.player1.license_number,
                "phone": pair.player1.phone,
                "ranking": 300,  # same as DB — not an explicit change
            },
            "player2": {
                "last_name": pair.player2.last_name,
                "first_name": pair.player2.first_name,
                "license_number": pair.player2.license_number,
                "phone": pair.player2.phone,
                "ranking": pair.player2.ranking,  # same as DB
            },
        }
        response = auth_client.put(
            pair_detail_url(tournament.id, pair.id), data=payload, format="json"
        )
        assert response.status_code == 200

        # FFT must have been called with force=True for player1 (name changed)
        force_true_calls = [c for c in calls if c["force"] is True]
        assert force_true_calls, (
            "fill_rankings_for_players was never called with force=True "
            "despite player1 name being changed (ranking was same value as DB)"
        )
        force_pks = {p.pk for p in force_true_calls[0]["players"]}
        assert p1_pk in force_pks, (
            "player1 not in the force=True FFT call despite name change"
        )

    def test_put_name_changed_ranking_different_value_keeps_manual_ranking(
        self, auth_client, tournament, monkeypatch
    ):
        """PUT with name changed + ranking sent with a DIFFERENT value → manual ranking kept, FFT skipped.

        When the ranking value differs from DB, the caller intentionally changed it.
        FFT must not overwrite that explicit choice even if the name also changed.
        """
        calls = []

        def fake_fill(players, tournament, force=False):
            calls.append({"players": list(players), "force": force})

        monkeypatch.setattr(
            "apps.players.serializers.fill_rankings_for_players", fake_fill
        )

        pair = PairFactory(tournament=tournament)
        pair.player1.ranking = 300
        pair.player1.save()
        p1_pk = pair.player1.pk

        # PUT with a DIFFERENT ranking value (999) AND a changed name.
        # The ranking IS explicit because value != DB value → FFT must be skipped.
        payload = {
            "player1": {
                "last_name": "NomDifferent",
                "first_name": pair.player1.first_name,
                "license_number": pair.player1.license_number,
                "phone": pair.player1.phone,
                "ranking": 999,  # different from DB (300) → explicit change
            },
            "player2": {
                "last_name": pair.player2.last_name,
                "first_name": pair.player2.first_name,
                "license_number": pair.player2.license_number,
                "phone": pair.player2.phone,
                "ranking": pair.player2.ranking,
            },
        }
        response = auth_client.put(
            pair_detail_url(tournament.id, pair.id), data=payload, format="json"
        )
        assert response.status_code == 200

        pair.player1.refresh_from_db()
        assert pair.player1.ranking == 999

        # FFT must NOT have been called with force=True for player1
        for call in calls:
            if call["force"]:
                pks = {p.pk for p in call["players"]}
                assert p1_pk not in pks, (
                    "fill_rankings_for_players called with force=True for player1 "
                    "even though ranking was explicitly changed to a different value"
                )


# ---------------------------------------------------------------------------
# TestPairNotifiesPublicUpdate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPairNotifiesPublicUpdate:
    def test_create_notifies_pairs_and_tournament(self, auth_client, tournament):
        payload = {
            "player1": {
                "last_name": "Martin",
                "first_name": "Julien",
                "license_number": "NOTIF_CREATE001",
                "phone": "",
            },
            "player2": {
                "last_name": "Roux",
                "first_name": "Quentin",
                "license_number": "NOTIF_CREATE002",
                "phone": "",
            },
        }

        with patch("apps.players.views.notify_public_update") as mock_notify:
            response = auth_client.post(
                pairs_url(tournament.id), data=payload, format="json"
            )

        assert response.status_code == 201
        mock_notify.assert_called_once_with(
            tournament, Resource.PAIRS, Resource.TOURNAMENT
        )

    def test_update_notifies_pairs_and_tournament(self, auth_client, tournament):
        pair = PairFactory(tournament=tournament, weight=100.0)

        with patch("apps.players.views.notify_public_update") as mock_notify:
            response = auth_client.patch(
                pair_detail_url(tournament.id, pair.id),
                data={"weight": 750.0},
                format="json",
            )

        assert response.status_code == 200
        mock_notify.assert_called_once_with(
            tournament, Resource.PAIRS, Resource.TOURNAMENT
        )

    def test_destroy_notifies_pairs_and_tournament(self, auth_client, tournament):
        pair = PairFactory(tournament=tournament)

        with patch("apps.players.views.notify_public_update") as mock_notify:
            response = auth_client.delete(pair_detail_url(tournament.id, pair.id))

        assert response.status_code == 204
        mock_notify.assert_called_once_with(
            tournament, Resource.PAIRS, Resource.TOURNAMENT
        )
