import pytest

from apps.matches.models import Bracket, Match, Round
from apps.matches.services import generate_match_tree
from apps.matches.tests.factories import BracketFactory
from apps.players.models import Pair
from apps.players.tests.factories import PairFactory
from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory


def _score_url(tournament_id: int, match_id: int) -> str:
    return f"/api/v1/tournaments/{tournament_id}/matches/{match_id}/score/"


def _bracket_url(tournament_id: int) -> str:
    return f"/api/v1/tournaments/{tournament_id}/bracket/"


def _build_dim8_main_with_classification(
    tournament: Tournament,
) -> dict:
    """Build a dim=8 main bracket (4 QUART_DE_FINALE feeding 2 DEMIE_FINALE
    feeding 1 FINALE) plus its classification bracket "Places 5-8"
    (source_round=QUART_DE_FINALE, dimension=4) — the 4 quarts' losers
    land here, 2 per classification DEMIE_FINALE.

    Returns:
    {
        "main_bracket": Bracket,
        "quart1".."quart4": Match,
        "classification_bracket": Bracket,
        "classification_demie1": Match, "classification_demie2": Match,
        "pairs": {"q<N>p1": Pair, "q<N>p2": Pair for N in 1..4},
    }
    """
    main_bracket = BracketFactory(tournament=tournament, dimension=8)
    generate_match_tree(main_bracket, tournament.game_format)
    quart1, quart2, quart3, quart4 = Match.objects.filter(
        bracket=main_bracket, round=Round.QUART_DE_FINALE
    ).order_by("match_number")

    classification_bracket = BracketFactory(
        tournament=tournament,
        parent=main_bracket,
        dimension=4,
        source_round=Round.QUART_DE_FINALE,
    )
    generate_match_tree(classification_bracket, tournament.game_format)
    classification_demie1, classification_demie2 = Match.objects.filter(
        bracket=classification_bracket, round=Round.DEMIE_FINALE
    ).order_by("match_number")

    pairs: dict[str, Pair] = {}
    for n, quart in enumerate((quart1, quart2, quart3, quart4), start=1):
        p1 = PairFactory(tournament=tournament)
        p2 = PairFactory(tournament=tournament)
        quart.pair1 = p1
        quart.pair2 = p2
        quart.save(update_fields=["pair1", "pair2", "updated_at"])
        pairs[f"q{n}p1"] = p1
        pairs[f"q{n}p2"] = p2

    return {
        "main_bracket": main_bracket,
        "quart1": quart1,
        "quart2": quart2,
        "quart3": quart3,
        "quart4": quart4,
        "classification_bracket": classification_bracket,
        "classification_demie1": classification_demie1,
        "classification_demie2": classification_demie2,
        "pairs": pairs,
    }


def _build_dim4_main_with_classification(
    tournament: Tournament,
) -> dict:
    """Build a dim=4 main bracket (2 DEMIE_FINALE feeding 1 FINALE) plus its
    classification bracket "Places 3-4" (source_round=DEMIE_FINALE,
    dimension=2, a single FINALE match) — the classification bracket's
    losers from the main bracket's demies land here.

    Returns:
    {
        "main_bracket": Bracket,
        "demie1": Match, "demie2": Match, "finale": Match,
        "classification_bracket": Bracket,
        "classification_finale": Match,
        "pairs": {"d1p1": Pair, "d1p2": Pair, "d2p1": Pair, "d2p2": Pair},
    }
    """
    main_bracket = BracketFactory(tournament=tournament, dimension=4)
    finale = generate_match_tree(main_bracket, tournament.game_format)
    demie1, demie2 = Match.objects.filter(
        bracket=main_bracket, round=Round.DEMIE_FINALE
    ).order_by("match_number")

    classification_bracket = BracketFactory(
        tournament=tournament,
        parent=main_bracket,
        dimension=2,
        source_round=Round.DEMIE_FINALE,
    )
    classification_finale = generate_match_tree(
        classification_bracket, tournament.game_format
    )

    d1p1 = PairFactory(tournament=tournament)
    d1p2 = PairFactory(tournament=tournament)
    d2p1 = PairFactory(tournament=tournament)
    d2p2 = PairFactory(tournament=tournament)

    demie1.pair1 = d1p1
    demie1.pair2 = d1p2
    demie1.save(update_fields=["pair1", "pair2", "updated_at"])
    demie2.pair1 = d2p1
    demie2.pair2 = d2p2
    demie2.save(update_fields=["pair1", "pair2", "updated_at"])

    return {
        "main_bracket": main_bracket,
        "demie1": demie1,
        "demie2": demie2,
        "finale": finale,
        "classification_bracket": classification_bracket,
        "classification_finale": classification_finale,
        "pairs": {"d1p1": d1p1, "d1p2": d1p2, "d2p1": d2p1, "d2p2": d2p2},
    }


@pytest.mark.django_db
class TestLoserPropagationOnScore:
    def test_loser_becomes_pair1_of_first_classification_match(
        self, authenticated_client, tournament
    ):
        tree = _build_dim4_main_with_classification(tournament)
        demie1 = tree["demie1"]
        d1p1 = tree["pairs"]["d1p1"]
        d1p2 = tree["pairs"]["d1p2"]

        resp = authenticated_client.patch(
            _score_url(tournament.pk, demie1.pk),
            {"score": "6/4 6/4", "winner_id": d1p1.pk},
            format="json",
        )

        assert resp.status_code == 200
        classification_finale = tree["classification_finale"]
        classification_finale.refresh_from_db()
        assert classification_finale.pair1_id == d1p2.pk

    def test_loser_becomes_pair2_of_first_classification_match(
        self, authenticated_client, tournament
    ):
        tree = _build_dim4_main_with_classification(tournament)
        demie2 = tree["demie2"]
        d2p1 = tree["pairs"]["d2p1"]
        d2p2 = tree["pairs"]["d2p2"]

        resp = authenticated_client.patch(
            _score_url(tournament.pk, demie2.pk),
            {"score": "6/4 6/4", "winner_id": d2p1.pk},
            format="json",
        )

        assert resp.status_code == 200
        classification_finale = tree["classification_finale"]
        classification_finale.refresh_from_db()
        assert classification_finale.pair2_id == d2p2.pk

    def test_losers_of_quart3_and_quart4_land_in_second_classification_match(
        self, authenticated_client, tournament
    ):
        tree = _build_dim8_main_with_classification(tournament)
        quart3 = tree["quart3"]
        quart4 = tree["quart4"]
        pairs = tree["pairs"]

        resp3 = authenticated_client.patch(
            _score_url(tournament.pk, quart3.pk),
            {"score": "6/4 6/4", "winner_id": pairs["q3p1"].pk},
            format="json",
        )
        resp4 = authenticated_client.patch(
            _score_url(tournament.pk, quart4.pk),
            {"score": "6/4 6/4", "winner_id": pairs["q4p1"].pk},
            format="json",
        )

        assert resp3.status_code == 200
        assert resp4.status_code == 200
        classification_demie2 = tree["classification_demie2"]
        classification_demie2.refresh_from_db()
        assert classification_demie2.pair1_id == pairs["q3p2"].pk
        assert classification_demie2.pair2_id == pairs["q4p2"].pk

    def test_ticket_example_dimension_16_12_pairs_active_huitiemes(
        self, authenticated_client, user
    ):
        """dimension=16, 12 pairs, nb_pair_round_16=8, nb_pair_round_8=4:
        active (non-disabled) huitiemes are #2, #4, #5, #7 (the others are
        disabled because their parent quart slot is filled directly by a
        round_8 entrant). The classification bracket "Places 9-12"
        (source_round=HUITIEME_DE_FINALE, dimension=4) must receive losers
        in *structural position* order (0,1,2,3 among the active matches
        sorted by match_number), regardless of the order scores are
        actually entered: loser #2 (position 0) -> match1.pair1, loser #4
        (position 1) -> match1.pair2, loser #5 (position 2) -> match2.pair1,
        loser #7 (position 3) -> match2.pair2.
        """
        t = TournamentFactory(owner=user)
        PairFactory.create_batch(12, tournament=t)

        resp = authenticated_client.post(
            _bracket_url(t.pk),
            {
                "dimension": 16,
                "nb_pair_round_64": 0,
                "nb_pair_round_32": 0,
                "nb_pair_round_16": 8,
                "nb_pair_round_8": 4,
                "nb_pair_round_4": 0,
            },
            format="json",
        )
        assert resp.status_code == 201

        main_bracket = Bracket.objects.get(tournament=t, parent__isnull=True)
        huitieme2, huitieme4, huitieme5, huitieme7 = (
            Match.objects.get(
                bracket=main_bracket,
                round=Round.HUITIEME_DE_FINALE,
                match_number=n,
            )
            for n in (2, 4, 5, 7)
        )
        for huitieme in (huitieme2, huitieme4, huitieme5, huitieme7):
            assert huitieme.disabled is False

        pairs: dict[str, Pair] = {}
        for n, huitieme in zip(
            (2, 4, 5, 7), (huitieme2, huitieme4, huitieme5, huitieme7), strict=True
        ):
            p1 = PairFactory(tournament=t)
            p2 = PairFactory(tournament=t)
            huitieme.pair1 = p1
            huitieme.pair2 = p2
            huitieme.save(update_fields=["pair1", "pair2", "updated_at"])
            pairs[f"h{n}p1"] = p1
            pairs[f"h{n}p2"] = p2

        # Score out of match_number order: #7, #2, #5, #4 — to prove only
        # structural position matters, not temporal scoring order.
        for n in (7, 2, 5, 4):
            huitieme = {2: huitieme2, 4: huitieme4, 5: huitieme5, 7: huitieme7}[n]
            resp = authenticated_client.patch(
                _score_url(t.pk, huitieme.pk),
                {"score": "6/4 6/4", "winner_id": pairs[f"h{n}p1"].pk},
                format="json",
            )
            assert resp.status_code == 200

        classification_bracket = Bracket.objects.get(
            parent=main_bracket, source_round=Round.HUITIEME_DE_FINALE
        )
        cmatch1, cmatch2 = Match.objects.filter(
            bracket=classification_bracket, round=Round.DEMIE_FINALE
        ).order_by("match_number")
        cmatch1.refresh_from_db()
        cmatch2.refresh_from_db()

        assert cmatch1.pair1_id == pairs["h2p2"].pk
        assert cmatch1.pair2_id == pairs["h4p2"].pk
        assert cmatch2.pair1_id == pairs["h5p2"].pk
        assert cmatch2.pair2_id == pairs["h7p2"].pk


def _build_classification_bracket_with_cascade_child(
    tournament: Tournament,
) -> dict:
    """Build a standalone classification bracket of dimension=4 (2
    DEMIE_FINALE feeding 1 FINALE), with its own cascade child of
    dimension=2 (parent=classification_bracket,
    source_round=DEMIE_FINALE, dimension=2 — a single FINALE match)
    receiving the losers of the dimension=4 bracket's 2 DEMIE_FINALE.

    Returns:
    {
        "classification_bracket": Bracket,
        "demie1": Match, "demie2": Match, "finale": Match,
        "cascade_child_bracket": Bracket, "cascade_finale": Match,
        "pairs": {"d1p1": Pair, "d1p2": Pair, "d2p1": Pair, "d2p2": Pair},
    }
    """
    classification_bracket = BracketFactory(
        tournament=tournament,
        parent=None,
        dimension=4,
        source_round=Round.QUART_DE_FINALE,
        start_place=9,
        end_place=12,
    )
    finale = generate_match_tree(classification_bracket, tournament.game_format)
    demie1, demie2 = Match.objects.filter(
        bracket=classification_bracket, round=Round.DEMIE_FINALE
    ).order_by("match_number")

    cascade_child_bracket = BracketFactory(
        tournament=tournament,
        parent=classification_bracket,
        dimension=2,
        source_round=Round.DEMIE_FINALE,
        start_place=11,
        end_place=12,
    )
    cascade_finale = generate_match_tree(
        cascade_child_bracket, tournament.game_format
    )

    d1p1 = PairFactory(tournament=tournament)
    d1p2 = PairFactory(tournament=tournament)
    d2p1 = PairFactory(tournament=tournament)
    d2p2 = PairFactory(tournament=tournament)

    demie1.pair1 = d1p1
    demie1.pair2 = d1p2
    demie1.save(update_fields=["pair1", "pair2", "updated_at"])
    demie2.pair1 = d2p1
    demie2.pair2 = d2p2
    demie2.save(update_fields=["pair1", "pair2", "updated_at"])

    return {
        "classification_bracket": classification_bracket,
        "demie1": demie1,
        "demie2": demie2,
        "finale": finale,
        "cascade_child_bracket": cascade_child_bracket,
        "cascade_finale": cascade_finale,
        "pairs": {"d1p1": d1p1, "d1p2": d1p2, "d2p1": d2p1, "d2p2": d2p2},
    }


@pytest.mark.django_db
class TestLoserPropagationCascade:
    def test_losers_of_demies_land_in_cascade_child_finale(
        self, authenticated_client, tournament
    ):
        tree = _build_classification_bracket_with_cascade_child(tournament)
        demie1 = tree["demie1"]
        demie2 = tree["demie2"]
        pairs = tree["pairs"]

        authenticated_client.patch(
            _score_url(tournament.pk, demie1.pk),
            {"score": "6/4 6/4", "winner_id": pairs["d1p1"].pk},
            format="json",
        )
        authenticated_client.patch(
            _score_url(tournament.pk, demie2.pk),
            {"score": "6/4 6/4", "winner_id": pairs["d2p1"].pk},
            format="json",
        )

        cascade_finale = tree["cascade_finale"]
        cascade_finale.refresh_from_db()
        assert cascade_finale.pair1_id == pairs["d1p2"].pk
        assert cascade_finale.pair2_id == pairs["d2p2"].pk

    def test_winners_of_demies_still_feed_own_bracket_finale(
        self, authenticated_client, tournament
    ):
        """Non-regression: winner propagation (_propagate_winner) must keep
        working unchanged inside a classification bracket that also
        cascades losers to its own child bracket.
        """
        tree = _build_classification_bracket_with_cascade_child(tournament)
        demie1 = tree["demie1"]
        demie2 = tree["demie2"]
        pairs = tree["pairs"]

        authenticated_client.patch(
            _score_url(tournament.pk, demie1.pk),
            {"score": "6/4 6/4", "winner_id": pairs["d1p1"].pk},
            format="json",
        )
        authenticated_client.patch(
            _score_url(tournament.pk, demie2.pk),
            {"score": "6/4 6/4", "winner_id": pairs["d2p1"].pk},
            format="json",
        )

        finale = tree["finale"]
        finale.refresh_from_db()
        assert finale.pair1_id == pairs["d1p1"].pk
        assert finale.pair2_id == pairs["d2p1"].pk


@pytest.mark.django_db
class TestLoserPropagationNoop:
    def test_round_without_any_classification_bracket_child_is_a_noop(
        self, authenticated_client, tournament
    ):
        bracket = BracketFactory(tournament=tournament, dimension=4)
        generate_match_tree(bracket, tournament.game_format)
        demie1 = Match.objects.get(
            bracket=bracket, round=Round.DEMIE_FINALE, match_number=1
        )
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        demie1.pair1 = pair1
        demie1.pair2 = pair2
        demie1.save(update_fields=["pair1", "pair2", "updated_at"])

        resp = authenticated_client.patch(
            _score_url(tournament.pk, demie1.pk),
            {"score": "6/4 6/4", "winner_id": pair1.pk},
            format="json",
        )

        assert resp.status_code == 200

    def test_classification_bracket_for_other_source_round_is_unaffected(
        self, authenticated_client, tournament
    ):
        main_bracket = BracketFactory(tournament=tournament, dimension=8)
        generate_match_tree(main_bracket, tournament.game_format)
        quart1 = Match.objects.get(
            bracket=main_bracket, round=Round.QUART_DE_FINALE, match_number=1
        )
        pair1 = PairFactory(tournament=tournament)
        pair2 = PairFactory(tournament=tournament)
        quart1.pair1 = pair1
        quart1.pair2 = pair2
        quart1.save(update_fields=["pair1", "pair2", "updated_at"])

        # Classification bracket exists, but for DEMIE_FINALE, not for
        # QUART_DE_FINALE (the round being scored) — must stay untouched.
        other_classification_bracket = BracketFactory(
            tournament=tournament,
            parent=main_bracket,
            dimension=2,
            source_round=Round.DEMIE_FINALE,
        )
        other_finale = generate_match_tree(
            other_classification_bracket, tournament.game_format
        )

        resp = authenticated_client.patch(
            _score_url(tournament.pk, quart1.pk),
            {"score": "6/4 6/4", "winner_id": pair1.pk},
            format="json",
        )

        assert resp.status_code == 200
        other_finale.refresh_from_db()
        assert other_finale.pair1_id is None
        assert other_finale.pair2_id is None


@pytest.mark.django_db
class TestLoserPropagationDelete:
    def test_delete_resets_loser_slot_in_classification_bracket(
        self, authenticated_client, tournament
    ):
        tree = _build_dim4_main_with_classification(tournament)
        demie1 = tree["demie1"]
        d1p1 = tree["pairs"]["d1p1"]

        authenticated_client.patch(
            _score_url(tournament.pk, demie1.pk),
            {"score": "6/4 6/4", "winner_id": d1p1.pk},
            format="json",
        )
        classification_finale = tree["classification_finale"]
        classification_finale.refresh_from_db()
        assert classification_finale.pair1_id is not None

        resp = authenticated_client.delete(_score_url(tournament.pk, demie1.pk))

        assert resp.status_code == 204
        classification_finale.refresh_from_db()
        assert classification_finale.pair1_id is None

    def test_204_when_classification_target_has_no_score_yet(
        self, authenticated_client, tournament
    ):
        tree = _build_dim4_main_with_classification(tournament)
        demie1 = tree["demie1"]
        d1p1 = tree["pairs"]["d1p1"]

        authenticated_client.patch(
            _score_url(tournament.pk, demie1.pk),
            {"score": "6/4 6/4", "winner_id": d1p1.pk},
            format="json",
        )
        classification_finale = tree["classification_finale"]
        classification_finale.refresh_from_db()
        assert classification_finale.winner_id is None

        resp = authenticated_client.delete(_score_url(tournament.pk, demie1.pk))

        assert resp.status_code == 204

    def test_409_when_classification_target_already_has_winner(
        self, authenticated_client, tournament
    ):
        tree = _build_dim4_main_with_classification(tournament)
        demie1 = tree["demie1"]
        demie2 = tree["demie2"]
        d1p1, d1p2 = tree["pairs"]["d1p1"], tree["pairs"]["d1p2"]
        d2p1, d2p2 = tree["pairs"]["d2p1"], tree["pairs"]["d2p2"]

        authenticated_client.patch(
            _score_url(tournament.pk, demie1.pk),
            {"score": "6/4 6/4", "winner_id": d1p1.pk},
            format="json",
        )
        authenticated_client.patch(
            _score_url(tournament.pk, demie2.pk),
            {"score": "6/4 6/4", "winner_id": d2p1.pk},
            format="json",
        )

        classification_finale = tree["classification_finale"]
        classification_finale.refresh_from_db()
        assert classification_finale.pair1_id == d1p2.pk
        assert classification_finale.pair2_id == d2p2.pk

        classification_resp = authenticated_client.patch(
            _score_url(tournament.pk, classification_finale.pk),
            {"score": "6/4 6/4", "winner_id": d1p2.pk},
            format="json",
        )
        assert classification_resp.status_code == 200

        resp = authenticated_client.delete(_score_url(tournament.pk, demie1.pk))

        assert resp.status_code == 409
        demie1.refresh_from_db()
        assert demie1.winner_id == d1p1.pk
        assert demie1.score != ""
        classification_finale.refresh_from_db()
        assert classification_finale.pair1_id == d1p2.pk
        assert classification_finale.winner_id == d1p2.pk


@pytest.mark.django_db
class TestTournamentStatusWithClassificationBrackets:
    """Locks in the bug fix: a classification bracket's own FINALE
    (e.g. "Places 3-4") must never be confused with the main bracket's
    FINALE when advancing/reverting tournament status — only
    `bracket.parent_id is None` identifies the real, tournament-deciding
    FINALE.
    """

    def test_scoring_classification_finale_does_not_finish_tournament(
        self, authenticated_client, tournament
    ):
        tree = _build_dim4_main_with_classification(tournament)
        tournament.status = Tournament.Status.STARTED
        tournament.save(update_fields=["status", "updated_at"])

        classification_finale = tree["classification_finale"]
        d1p2 = tree["pairs"]["d1p2"]
        classification_finale.pair1 = d1p2
        classification_finale.pair2 = tree["pairs"]["d2p2"]
        classification_finale.save(
            update_fields=["pair1", "pair2", "updated_at"]
        )

        resp = authenticated_client.patch(
            _score_url(tournament.pk, classification_finale.pk),
            {"score": "6/4 6/4", "winner_id": d1p2.pk},
            format="json",
        )

        assert resp.status_code == 200
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.STARTED

    def test_deleting_classification_finale_score_does_not_revert_tournament(
        self, authenticated_client, tournament
    ):
        tree = _build_dim4_main_with_classification(tournament)
        finale = tree["finale"]
        demie1, demie2 = tree["demie1"], tree["demie2"]
        d1p1, d2p1 = tree["pairs"]["d1p1"], tree["pairs"]["d2p1"]

        authenticated_client.patch(
            _score_url(tournament.pk, demie1.pk),
            {"score": "6/4 6/4", "winner_id": d1p1.pk},
            format="json",
        )
        authenticated_client.patch(
            _score_url(tournament.pk, demie2.pk),
            {"score": "6/4 6/4", "winner_id": d2p1.pk},
            format="json",
        )
        finale.refresh_from_db()
        authenticated_client.patch(
            _score_url(tournament.pk, finale.pk),
            {"score": "6/4 6/4", "winner_id": d1p1.pk},
            format="json",
        )
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED

        classification_finale = tree["classification_finale"]
        classification_finale.refresh_from_db()
        d1p2 = tree["pairs"]["d1p2"]
        authenticated_client.patch(
            _score_url(tournament.pk, classification_finale.pk),
            {"score": "6/4 6/4", "winner_id": d1p2.pk},
            format="json",
        )
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED

        resp = authenticated_client.delete(
            _score_url(tournament.pk, classification_finale.pk)
        )

        assert resp.status_code == 204
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED

    def test_scoring_main_bracket_finale_still_finishes_tournament(
        self, authenticated_client, tournament
    ):
        """Non-regression: scoring the real FINALE still finishes the
        tournament even though classification brackets exist alongside it.
        """
        tree = _build_dim4_main_with_classification(tournament)
        finale = tree["finale"]
        demie1, demie2 = tree["demie1"], tree["demie2"]
        d1p1, d2p1 = tree["pairs"]["d1p1"], tree["pairs"]["d2p1"]

        authenticated_client.patch(
            _score_url(tournament.pk, demie1.pk),
            {"score": "6/4 6/4", "winner_id": d1p1.pk},
            format="json",
        )
        authenticated_client.patch(
            _score_url(tournament.pk, demie2.pk),
            {"score": "6/4 6/4", "winner_id": d2p1.pk},
            format="json",
        )
        finale.refresh_from_db()

        resp = authenticated_client.patch(
            _score_url(tournament.pk, finale.pk),
            {"score": "6/4 6/4", "winner_id": d1p1.pk},
            format="json",
        )

        assert resp.status_code == 200
        tournament.refresh_from_db()
        assert tournament.status == Tournament.Status.FINISHED


@pytest.mark.django_db
class TestWinnerPropagationInsideClassificationBracket:
    """Characterization / lock-in test: `_propagate_winner`/`_find_parent_slot`
    never filter by bracket — they only follow `child1`/`child2` /
    `parent_as_child1`/`parent_as_child2` relations, which
    `generate_match_tree` sets up identically for every bracket. So winner
    propagation should already work natively *inside* a classification
    bracket, exactly as it does in the main bracket. This test guards
    against any future regression that would accidentally scope winner
    propagation to the main bracket only.
    """

    def test_winners_of_demies_propagate_to_own_finale_pair1_and_pair2(
        self, authenticated_client, tournament
    ):
        classification_bracket = BracketFactory(
            tournament=tournament,
            parent=None,
            dimension=4,
            source_round=Round.QUART_DE_FINALE,
            start_place=9,
            end_place=12,
        )
        finale = generate_match_tree(classification_bracket, tournament.game_format)
        demie1, demie2 = Match.objects.filter(
            bracket=classification_bracket, round=Round.DEMIE_FINALE
        ).order_by("match_number")

        d1p1 = PairFactory(tournament=tournament)
        d1p2 = PairFactory(tournament=tournament)
        d2p1 = PairFactory(tournament=tournament)
        d2p2 = PairFactory(tournament=tournament)
        demie1.pair1 = d1p1
        demie1.pair2 = d1p2
        demie1.save(update_fields=["pair1", "pair2", "updated_at"])
        demie2.pair1 = d2p1
        demie2.pair2 = d2p2
        demie2.save(update_fields=["pair1", "pair2", "updated_at"])

        resp1 = authenticated_client.patch(
            _score_url(tournament.pk, demie1.pk),
            {"score": "6/4 6/4", "winner_id": d1p1.pk},
            format="json",
        )
        resp2 = authenticated_client.patch(
            _score_url(tournament.pk, demie2.pk),
            {"score": "6/4 6/4", "winner_id": d2p2.pk},
            format="json",
        )

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        finale.refresh_from_db()
        assert finale.pair1_id == d1p1.pk
        assert finale.pair2_id == d2p2.pk
