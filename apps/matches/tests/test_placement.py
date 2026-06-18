import pytest
from rest_framework.test import APIClient

from apps.matches.models import Bracket, Match, Round
from apps.players.tests.factories import PairFactory
from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory


def placement_url(tournament_id: int) -> str:
    return f"/api/v1/tournaments/{tournament_id}/bracket/placement/"


def _zero_seeding() -> dict:
    return {
        "nb_pair_round_64": 0,
        "nb_pair_round_32": 0,
        "nb_pair_round_16": 0,
        "nb_pair_round_8": 0,
        "nb_pair_round_4": 0,
    }


@pytest.fixture
def bracket(authenticated_client, tournament):
    authenticated_client.post(
        f"/api/v1/tournaments/{tournament.pk}/bracket/",
        {"dimension": 8, **_zero_seeding()},
        format="json",
    )
    return Bracket.objects.get(tournament=tournament)


@pytest.fixture
def leaf_matches(bracket):
    return list(
        Match.objects.filter(bracket=bracket, child1__isnull=True).order_by(
            "match_number"
        )
    )


@pytest.fixture
def second_round_matches(bracket):
    return list(
        Match.objects.filter(bracket=bracket, round=Round.DEMIE_FINALE).order_by(
            "match_number"
        )
    )


@pytest.fixture
def pairs(tournament):
    return [PairFactory(tournament=tournament) for _ in range(8)]


@pytest.mark.django_db
class TestBracketPlacement:
    def test_partial_placement_saves_pairs(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        payload = {
            "placements": [
                {
                    "match_id": leaf_matches[0].pk,
                    "pair1_id": pairs[0].pk,
                    "pair2_id": pairs[1].pk,
                },
                {
                    "match_id": leaf_matches[1].pk,
                    "pair1_id": pairs[2].pk,
                    "pair2_id": pairs[3].pk,
                },
            ]
        }
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 200

        leaf_matches[0].refresh_from_db()
        leaf_matches[1].refresh_from_db()
        leaf_matches[2].refresh_from_db()

        assert leaf_matches[0].pair1_id == pairs[0].pk
        assert leaf_matches[0].pair2_id == pairs[1].pk
        assert leaf_matches[1].pair1_id == pairs[2].pk
        assert leaf_matches[1].pair2_id == pairs[3].pk
        assert leaf_matches[2].pair1_id is None
        assert leaf_matches[2].pair2_id is None

    def test_top_seed_placed_in_second_round(
        self, authenticated_client, tournament, bracket, second_round_matches, pairs
    ):
        payload = {
            "placements": [
                {
                    "match_id": second_round_matches[0].pk,
                    "pair1_id": pairs[0].pk,
                    "pair2_id": None,
                },
            ]
        }
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 200

        second_round_matches[0].refresh_from_db()
        assert second_round_matches[0].pair1_id == pairs[0].pk
        assert second_round_matches[0].pair2_id is None

    def test_null_pair_unplaces_existing_pair(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        leaf_matches[0].pair1 = pairs[0]
        leaf_matches[0].save()

        payload = {
            "placements": [
                {"match_id": leaf_matches[0].pk, "pair1_id": None, "pair2_id": None},
            ]
        }
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 200

        leaf_matches[0].refresh_from_db()
        assert leaf_matches[0].pair1_id is None

    def test_response_is_full_bracket(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        payload = {
            "placements": [
                {
                    "match_id": leaf_matches[0].pk,
                    "pair1_id": pairs[0].pk,
                    "pair2_id": pairs[1].pk,
                },
            ]
        }
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "dimension" in data
        assert "root_match" in data
        assert data["root_match"]["round"] == "FINALE"

    def test_400_match_not_in_tournament_bracket(
        self, authenticated_client, tournament, bracket, pairs
    ):
        other_tournament = TournamentFactory(owner=tournament.owner)
        other_bracket = Bracket.objects.create(tournament=other_tournament, dimension=8)
        other_match = Match.objects.create(
            bracket=other_bracket,
            round=Round.QUART_DE_FINALE,
            match_number=1,
        )
        payload = {
            "placements": [
                {"match_id": other_match.pk, "pair1_id": pairs[0].pk, "pair2_id": None},
            ]
        }
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 400

    def test_400_match_already_scored(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        leaf_matches[0].score = "6-4 6-3"
        leaf_matches[0].save()

        payload = {
            "placements": [
                {
                    "match_id": leaf_matches[0].pk,
                    "pair1_id": pairs[0].pk,
                    "pair2_id": pairs[1].pk,
                },
            ]
        }
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 400

    def test_400_pair_not_in_tournament(
        self, authenticated_client, tournament, bracket, leaf_matches
    ):
        other_pair = PairFactory()
        payload = {
            "placements": [
                {
                    "match_id": leaf_matches[0].pk,
                    "pair1_id": other_pair.pk,
                    "pair2_id": None,
                },
            ]
        }
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 400

    def test_400_same_pair_twice_in_request(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        payload = {
            "placements": [
                {
                    "match_id": leaf_matches[0].pk,
                    "pair1_id": pairs[0].pk,
                    "pair2_id": None,
                },
                {
                    "match_id": leaf_matches[1].pk,
                    "pair1_id": pairs[0].pk,
                    "pair2_id": None,
                },
            ]
        }
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 400

    def test_400_pair_already_placed_in_other_match(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        leaf_matches[2].pair1 = pairs[0]
        leaf_matches[2].save()

        payload = {
            "placements": [
                {
                    "match_id": leaf_matches[0].pk,
                    "pair1_id": pairs[0].pk,
                    "pair2_id": None,
                },
            ]
        }
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 400

    def test_400_pair1_same_as_pair2(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        payload = {
            "placements": [
                {
                    "match_id": leaf_matches[0].pk,
                    "pair1_id": pairs[0].pk,
                    "pair2_id": pairs[0].pk,
                },
            ]
        }
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 400

    def test_401_unauthenticated(self, tournament, bracket, leaf_matches, pairs):
        anon = APIClient()
        payload = {
            "placements": [
                {
                    "match_id": leaf_matches[0].pk,
                    "pair1_id": pairs[0].pk,
                    "pair2_id": None,
                },
            ]
        }
        resp = anon.patch(placement_url(tournament.pk), payload, format="json")
        assert resp.status_code == 401

    def test_404_non_owner(self, tournament, bracket, leaf_matches, pairs):
        other = UserFactory()
        other_client = APIClient()
        other_client.force_authenticate(user=other)
        payload = {
            "placements": [
                {
                    "match_id": leaf_matches[0].pk,
                    "pair1_id": pairs[0].pk,
                    "pair2_id": None,
                },
            ]
        }
        resp = other_client.patch(placement_url(tournament.pk), payload, format="json")
        assert resp.status_code == 404

    def test_404_no_bracket(self, authenticated_client, tournament):
        payload = {"placements": []}
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestBracketPlacementCascade:
    def test_bypass_placement_on_semifinal_disables_corresponding_quarter(
        self,
        authenticated_client,
        tournament,
        bracket,
        second_round_matches,
        leaf_matches,
        pairs,
    ):
        demie1 = second_round_matches[0]
        quart1 = Match.objects.get(pk=demie1.child1_id)
        quart2 = Match.objects.get(pk=demie1.child2_id)

        payload = {
            "placements": [
                {"match_id": demie1.pk, "pair1_id": pairs[0].pk, "pair2_id": None},
            ]
        }
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 200

        quart1.refresh_from_db()
        quart2.refresh_from_db()
        assert quart1.disabled is True
        assert quart1.pair1_can_be_placed is False
        assert quart1.pair2_can_be_placed is False
        assert quart2.disabled is False
        assert quart2.pair1_can_be_placed is True
        assert quart2.pair2_can_be_placed is True

    def test_bypass_placement_on_semifinal_pair2_disables_other_quarter(
        self, authenticated_client, tournament, bracket, second_round_matches, pairs
    ):
        demie1 = second_round_matches[0]
        quart1 = Match.objects.get(pk=demie1.child1_id)
        quart2 = Match.objects.get(pk=demie1.child2_id)

        payload = {
            "placements": [
                {"match_id": demie1.pk, "pair1_id": None, "pair2_id": pairs[0].pk},
            ]
        }
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 200

        quart1.refresh_from_db()
        quart2.refresh_from_db()
        assert quart2.disabled is True
        assert quart2.pair1_can_be_placed is False
        assert quart2.pair2_can_be_placed is False
        assert quart1.disabled is False
        assert quart1.pair1_can_be_placed is True
        assert quart1.pair2_can_be_placed is True

    def test_leaf_placement_blocks_parent_and_grandparent_slot(
        self,
        authenticated_client,
        tournament,
        bracket,
        leaf_matches,
        second_round_matches,
        pairs,
    ):
        quart1 = leaf_matches[0]
        demie1 = quart1.parent_as_child1.get()
        finale = Match.objects.get(round="FINALE")

        payload = {
            "placements": [
                {
                    "match_id": quart1.pk,
                    "pair1_id": pairs[0].pk,
                    "pair2_id": pairs[1].pk,
                },
            ]
        }
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 200

        demie1.refresh_from_db()
        finale.refresh_from_db()
        assert demie1.pair1_can_be_placed is False
        assert finale.pair1_can_be_placed is False

    def test_reversal_reenables_quarter(
        self, authenticated_client, tournament, bracket, second_round_matches, pairs
    ):
        demie1 = second_round_matches[0]
        quart1 = Match.objects.get(pk=demie1.child1_id)

        authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {"match_id": demie1.pk, "pair1_id": pairs[0].pk, "pair2_id": None}
                ]
            },
            format="json",
        )
        quart1.refresh_from_db()
        assert quart1.disabled is True

        resp = authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {"match_id": demie1.pk, "pair1_id": None, "pair2_id": None}
                ]
            },
            format="json",
        )
        assert resp.status_code == 200

        quart1.refresh_from_db()
        assert quart1.disabled is False
        assert quart1.pair1_can_be_placed is True
        assert quart1.pair2_can_be_placed is True

    def test_reversal_still_blocked_when_sibling_quarter_still_placed(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        quart1, quart2 = leaf_matches[0], leaf_matches[1]
        finale = Match.objects.get(round="FINALE")

        authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {"match_id": quart1.pk, "pair1_id": pairs[0].pk, "pair2_id": None},
                    {"match_id": quart2.pk, "pair1_id": pairs[1].pk, "pair2_id": None},
                ]
            },
            format="json",
        )
        finale.refresh_from_db()
        assert finale.pair1_can_be_placed is False

        resp = authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {"match_id": quart1.pk, "pair1_id": None, "pair2_id": None}
                ]
            },
            format="json",
        )
        assert resp.status_code == 200

        finale.refresh_from_db()
        assert finale.pair1_can_be_placed is False

    def test_400_placement_into_disabled_match(
        self,
        authenticated_client,
        tournament,
        bracket,
        second_round_matches,
        leaf_matches,
        pairs,
    ):
        demie1 = second_round_matches[0]
        quart1 = Match.objects.get(pk=demie1.child1_id)

        authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {"match_id": demie1.pk, "pair1_id": pairs[0].pk, "pair2_id": None}
                ]
            },
            format="json",
        )
        quart1.refresh_from_db()
        assert quart1.disabled is True

        resp = authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {
                        "match_id": quart1.pk,
                        "pair1_id": pairs[1].pk,
                        "pair2_id": pairs[2].pk,
                    }
                ]
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_400_placement_into_disabled_match_pair2_only(
        self,
        authenticated_client,
        tournament,
        bracket,
        second_round_matches,
        leaf_matches,
        pairs,
    ):
        demie1 = second_round_matches[0]
        quart1 = Match.objects.get(pk=demie1.child1_id)

        authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {"match_id": demie1.pk, "pair1_id": pairs[0].pk, "pair2_id": None}
                ]
            },
            format="json",
        )
        quart1.refresh_from_db()
        assert quart1.disabled is True

        resp = authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {"match_id": quart1.pk, "pair1_id": None, "pair2_id": pairs[1].pk}
                ]
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_400_placement_into_slot_already_blocked(
        self,
        authenticated_client,
        tournament,
        bracket,
        leaf_matches,
        second_round_matches,
        pairs,
    ):
        quart1 = leaf_matches[0]
        demie1 = quart1.parent_as_child1.get()

        authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {
                        "match_id": quart1.pk,
                        "pair1_id": pairs[0].pk,
                        "pair2_id": pairs[1].pk,
                    }
                ]
            },
            format="json",
        )
        demie1.refresh_from_db()
        assert demie1.pair1_can_be_placed is False

        resp = authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {"match_id": demie1.pk, "pair1_id": pairs[2].pk, "pair2_id": None}
                ]
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_400_placement_into_slot_already_blocked_pair2(
        self,
        authenticated_client,
        tournament,
        bracket,
        leaf_matches,
        second_round_matches,
        pairs,
    ):
        quart2 = leaf_matches[1]
        demie1 = quart2.parent_as_child2.get()

        authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {
                        "match_id": quart2.pk,
                        "pair1_id": pairs[0].pk,
                        "pair2_id": pairs[1].pk,
                    }
                ]
            },
            format="json",
        )
        demie1.refresh_from_db()
        assert demie1.pair2_can_be_placed is False

        resp = authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {"match_id": demie1.pk, "pair1_id": None, "pair2_id": pairs[2].pk}
                ]
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_unplacing_disabled_match_slot_is_always_allowed(
        self, authenticated_client, tournament, bracket, second_round_matches, pairs
    ):
        """Setting a slot to null is always allowed, even on a disabled match
        (rule: un-placing bypasses the disabled/can_be_placed checks)."""
        demie1 = second_round_matches[0]
        quart1 = Match.objects.get(pk=demie1.child1_id)

        authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {"match_id": demie1.pk, "pair1_id": pairs[0].pk, "pair2_id": None}
                ]
            },
            format="json",
        )
        quart1.refresh_from_db()
        assert quart1.disabled is True

        # quart1 is disabled, but its slots are already null — patching it to
        # null again must not be rejected because of the disabled flag.
        resp = authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {"match_id": quart1.pk, "pair1_id": None, "pair2_id": None}
                ]
            },
            format="json",
        )
        assert resp.status_code == 200


@pytest.mark.django_db
class TestBracketPlacementDimension16Cascade:
    @pytest.fixture
    def bracket16(self, authenticated_client, tournament):
        authenticated_client.post(
            f"/api/v1/tournaments/{tournament.pk}/bracket/",
            {"dimension": 16, **_zero_seeding()},
            format="json",
        )
        return Bracket.objects.get(tournament=tournament)

    @staticmethod
    def _descendants(match: Match) -> list[Match]:
        """Recursively collect all descendants (children, grandchildren, ...) of a match."""
        result = []
        for child_id in (match.child1_id, match.child2_id):
            if child_id is None:
                continue
            child = Match.objects.get(pk=child_id)
            result.append(child)
            result.extend(TestBracketPlacementDimension16Cascade._descendants(child))
        return result

    def test_bypass_on_finale_cascades_two_levels_down(
        self, authenticated_client, tournament, bracket16, pairs
    ):
        finale = Match.objects.get(bracket=bracket16, round="FINALE")
        demie1 = Match.objects.get(pk=finale.child1_id)
        demie2 = Match.objects.get(pk=finale.child2_id)
        demie1_descendants = self._descendants(demie1)
        demie2_descendants = self._descendants(demie2)
        # dimension 16: each semifinal branch has 2 quarters + 4 eighths = 6 descendants
        assert len(demie1_descendants) == 6
        assert len(demie2_descendants) == 6

        resp = authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {"match_id": finale.pk, "pair1_id": pairs[0].pk, "pair2_id": None}
                ]
            },
            format="json",
        )
        assert resp.status_code == 200

        demie1.refresh_from_db()
        assert demie1.disabled is True
        assert demie1.pair1_can_be_placed is False
        assert demie1.pair2_can_be_placed is False

        for m in demie1_descendants:
            m.refresh_from_db()
            assert m.disabled is True
            assert m.pair1_can_be_placed is False
            assert m.pair2_can_be_placed is False

        demie2.refresh_from_db()
        assert demie2.disabled is False
        assert demie2.pair1_can_be_placed is True
        assert demie2.pair2_can_be_placed is True

        for m in demie2_descendants:
            m.refresh_from_db()
            assert m.disabled is False
            assert m.pair1_can_be_placed is True
            assert m.pair2_can_be_placed is True

    def test_unplacing_slot_while_resending_unchanged_propagated_slot_is_allowed(
        self, authenticated_client, tournament, bracket16, pairs
    ):
        """Regression test: a placement request must resend both pair1_id and
        pair2_id for a match, even when only one of them is actually changing.
        Resending the other slot's current (unchanged) value must not be
        treated as a new placement attempt, even if that slot's
        can_be_placed is False because it was filled by legitimate winner
        propagation from a played child match."""
        finale = Match.objects.get(bracket=bracket16, round="FINALE")
        demie1 = Match.objects.get(pk=finale.child1_id)
        quart1 = Match.objects.get(pk=demie1.child1_id)
        huitieme2 = Match.objects.get(pk=quart1.child2_id)

        # Bypass-place pair1 directly on quart1 (skips huitieme1 entirely).
        authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {"match_id": quart1.pk, "pair1_id": pairs[0].pk, "pair2_id": None}
                ]
            },
            format="json",
        )

        # Play huitieme2 normally; its winner propagates into quart1.pair2.
        authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {
                        "match_id": huitieme2.pk,
                        "pair1_id": pairs[1].pk,
                        "pair2_id": pairs[2].pk,
                    }
                ]
            },
            format="json",
        )
        score_url = f"/api/v1/tournaments/{tournament.pk}/matches/{huitieme2.pk}/score/"
        authenticated_client.patch(
            score_url, {"score": "6-4 6-2", "winner_id": pairs[1].pk}, format="json"
        )

        quart1.refresh_from_db()
        assert quart1.pair1_id == pairs[0].pk
        assert quart1.pair2_id == pairs[1].pk
        assert quart1.pair2_can_be_placed is False

        resp = authenticated_client.patch(
            placement_url(tournament.pk),
            {
                "placements": [
                    {
                        "match_id": quart1.pk,
                        "pair1_id": None,
                        "pair2_id": pairs[1].pk,
                    }
                ]
            },
            format="json",
        )
        assert resp.status_code == 200

        quart1.refresh_from_db()
        assert quart1.pair1_id is None
        assert quart1.pair2_id == pairs[1].pk


@pytest.mark.django_db
class TestBracketPlacementStatusRestriction:
    def test_409_when_tournament_finished(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        tournament.status = Tournament.Status.FINISHED
        tournament.save()

        payload = {
            "placements": [
                {
                    "match_id": leaf_matches[0].pk,
                    "pair1_id": pairs[0].pk,
                    "pair2_id": pairs[1].pk,
                },
            ]
        }
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 409

    def test_200_when_tournament_started(
        self, authenticated_client, tournament, bracket, leaf_matches, pairs
    ):
        """Explicitly allowed: placement remains editable while STARTED."""
        tournament.status = Tournament.Status.STARTED
        tournament.save()

        payload = {
            "placements": [
                {
                    "match_id": leaf_matches[0].pk,
                    "pair1_id": pairs[0].pk,
                    "pair2_id": pairs[1].pk,
                },
            ]
        }
        resp = authenticated_client.patch(
            placement_url(tournament.pk), payload, format="json"
        )
        assert resp.status_code == 200
