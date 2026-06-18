import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.tournaments.models import Tournament
from apps.tournaments.tests.factories import TournamentFactory
from apps.users.tests.factories import UserFactory

from .factories import FFTRankingFactory, PairFactory, PlayerFactory

URL = "/api/v1/tournaments/{tournament_id}/pairs/ranking-matching/"


def url(tournament_id: int) -> str:
    return URL.format(tournament_id=tournament_id)


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def tournament(user):
    return TournamentFactory(
        owner=user,
        gender=Tournament.Gender.MALE,
        league=Tournament.League.ILE_DE_FRANCE,
    )


# ---------------------------------------------------------------------------
# Auth & permissions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_unauthenticated_returns_401(tournament):
    response = APIClient().get(url(tournament.pk))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_tournament_not_found_returns_404(client):
    response = client.get(url(99999))
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_tournament_owned_by_other_user_returns_404(client):
    other_tournament = TournamentFactory()
    response = client.get(url(other_tournament.pk))
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_empty_tournament_returns_empty_list(client, tournament):
    response = client.get(url(tournament.pk))
    assert response.status_code == status.HTTP_200_OK
    assert response.data == []


# ---------------------------------------------------------------------------
# Statut du tournoi — blocage si STARTED/FINISHED
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_returns_409_when_tournament_started(client, tournament):
    player = PlayerFactory(ranking=None)
    FFTRankingFactory(
        last_name=player.last_name,
        first_name=player.first_name,
        ranking=42,
        gender=Tournament.Gender.MALE,
    )
    partner = PlayerFactory(ranking=None)
    pair = PairFactory(
        tournament=tournament, player1=player, player2=partner, weight=None
    )
    tournament.status = Tournament.Status.STARTED
    tournament.save()

    response = client.get(url(tournament.pk))

    assert response.status_code == status.HTTP_409_CONFLICT
    player.refresh_from_db()
    pair.refresh_from_db()
    assert player.ranking is None
    assert pair.weight is None


@pytest.mark.django_db
def test_returns_409_when_tournament_finished(client, tournament):
    player = PlayerFactory(ranking=None)
    FFTRankingFactory(
        last_name=player.last_name,
        first_name=player.first_name,
        ranking=42,
        gender=Tournament.Gender.MALE,
    )
    partner = PlayerFactory(ranking=None)
    pair = PairFactory(
        tournament=tournament, player1=player, player2=partner, weight=None
    )
    tournament.status = Tournament.Status.FINISHED
    tournament.save()

    response = client.get(url(tournament.pk))

    assert response.status_code == status.HTTP_409_CONFLICT
    player.refresh_from_db()
    pair.refresh_from_db()
    assert player.ranking is None
    assert pair.weight is None


# ---------------------------------------------------------------------------
# Matching — non-écrasement du classement existant
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_existing_ranking_not_overwritten(client, tournament):
    player = PlayerFactory(ranking=100)
    FFTRankingFactory(
        last_name=player.last_name,
        first_name=player.first_name,
        ranking=999,
        gender=Tournament.Gender.MALE,
    )
    partner = PlayerFactory(ranking=200)
    PairFactory(tournament=tournament, player1=player, player2=partner)

    client.get(url(tournament.pk))

    player.refresh_from_db()
    assert player.ranking == 100


# ---------------------------------------------------------------------------
# Matching — cas de base
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_single_match_updates_ranking(client, tournament):
    player = PlayerFactory(ranking=None)
    FFTRankingFactory(
        last_name=player.last_name,
        first_name=player.first_name,
        ranking=42,
        gender=Tournament.Gender.MALE,
    )
    partner = PlayerFactory(ranking=None)
    PairFactory(tournament=tournament, player1=player, player2=partner)

    client.get(url(tournament.pk))

    player.refresh_from_db()
    assert player.ranking == 42


@pytest.mark.django_db
def test_no_match_ranking_stays_none(client, tournament):
    player = PlayerFactory(ranking=None)
    partner = PlayerFactory(ranking=None)
    PairFactory(tournament=tournament, player1=player, player2=partner)

    client.get(url(tournament.pk))

    player.refresh_from_db()
    assert player.ranking is None


# ---------------------------------------------------------------------------
# Matching — gestion des homonymes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_homonyms_single_same_league_uses_ranking(client, tournament):
    player = PlayerFactory(ranking=None)
    FFTRankingFactory(
        last_name=player.last_name,
        first_name=player.first_name,
        ranking=10,
        league=Tournament.League.ILE_DE_FRANCE,
        gender=Tournament.Gender.MALE,
    )
    # homonyme d'une autre ligue
    FFTRankingFactory(
        last_name=player.last_name,
        first_name=player.first_name,
        ranking=20,
        league=Tournament.League.BRETAGNE,
        gender=Tournament.Gender.MALE,
    )
    partner = PlayerFactory(ranking=None)
    PairFactory(tournament=tournament, player1=player, player2=partner)

    client.get(url(tournament.pk))

    player.refresh_from_db()
    assert player.ranking == 10


@pytest.mark.django_db
def test_homonyms_none_in_same_league_ranking_stays_none(client, tournament):
    player = PlayerFactory(ranking=None)
    # deux homonymes, aucun dans la bonne ligue
    FFTRankingFactory(
        last_name=player.last_name,
        first_name=player.first_name,
        ranking=10,
        league=Tournament.League.BRETAGNE,
        gender=Tournament.Gender.MALE,
    )
    FFTRankingFactory(
        last_name=player.last_name,
        first_name=player.first_name,
        ranking=20,
        league=Tournament.League.NORMANDIE,
        gender=Tournament.Gender.MALE,
    )
    partner = PlayerFactory(ranking=None)
    PairFactory(tournament=tournament, player1=player, player2=partner)

    client.get(url(tournament.pk))

    player.refresh_from_db()
    assert player.ranking is None


@pytest.mark.django_db
def test_homonyms_multiple_in_same_league_ranking_stays_none(client, tournament):
    player = PlayerFactory(ranking=None)
    # deux homonymes dans la même ligue → ambiguïté
    FFTRankingFactory(
        last_name=player.last_name,
        first_name=player.first_name,
        ranking=10,
        league=Tournament.League.ILE_DE_FRANCE,
        gender=Tournament.Gender.MALE,
    )
    FFTRankingFactory(
        last_name=player.last_name,
        first_name=player.first_name,
        ranking=20,
        league=Tournament.League.ILE_DE_FRANCE,
        gender=Tournament.Gender.MALE,
    )
    partner = PlayerFactory(ranking=None)
    PairFactory(tournament=tournament, player1=player, player2=partner)

    client.get(url(tournament.pk))

    player.refresh_from_db()
    assert player.ranking is None


# ---------------------------------------------------------------------------
# Filtre genre
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_male_tournament_filters_male_rankings(client, user):
    tournament = TournamentFactory(
        owner=user,
        gender=Tournament.Gender.MALE,
        league=Tournament.League.ILE_DE_FRANCE,
    )
    player = PlayerFactory(ranking=None)
    # classement féminin — ne doit pas être utilisé
    FFTRankingFactory(
        last_name=player.last_name,
        first_name=player.first_name,
        ranking=50,
        gender=Tournament.Gender.FEMALE,
    )
    partner = PlayerFactory(ranking=None)
    PairFactory(tournament=tournament, player1=player, player2=partner)

    APIClient().force_authenticate(user=user)
    c = APIClient()
    c.force_authenticate(user=user)
    c.get(url(tournament.pk))

    player.refresh_from_db()
    assert player.ranking is None


@pytest.mark.django_db
def test_female_tournament_filters_female_rankings(client, user):
    tournament = TournamentFactory(
        owner=user,
        gender=Tournament.Gender.FEMALE,
        league=Tournament.League.ILE_DE_FRANCE,
    )
    player = PlayerFactory(ranking=None)
    # classement masculin — ne doit pas être utilisé
    FFTRankingFactory(
        last_name=player.last_name,
        first_name=player.first_name,
        ranking=50,
        gender=Tournament.Gender.MALE,
    )
    partner = PlayerFactory(ranking=None)
    PairFactory(tournament=tournament, player1=player, player2=partner)

    c = APIClient()
    c.force_authenticate(user=user)
    c.get(url(tournament.pk))

    player.refresh_from_db()
    assert player.ranking is None


@pytest.mark.django_db
def test_mixed_tournament_ignores_gender_filter(client, user):
    tournament = TournamentFactory(
        owner=user,
        gender=Tournament.Gender.MIXED,
        league=Tournament.League.ILE_DE_FRANCE,
    )
    player = PlayerFactory(ranking=None)
    FFTRankingFactory(
        last_name=player.last_name,
        first_name=player.first_name,
        ranking=77,
        gender=Tournament.Gender.FEMALE,
    )
    partner = PlayerFactory(ranking=None)
    PairFactory(tournament=tournament, player1=player, player2=partner)

    c = APIClient()
    c.force_authenticate(user=user)
    c.get(url(tournament.pk))

    player.refresh_from_db()
    assert player.ranking == 77


# ---------------------------------------------------------------------------
# Calcul du poids
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_weight_computed_when_both_have_ranking(client, tournament):
    player1 = PlayerFactory(ranking=None)
    player2 = PlayerFactory(ranking=None)
    FFTRankingFactory(
        last_name=player1.last_name,
        first_name=player1.first_name,
        ranking=100,
        gender=Tournament.Gender.MALE,
    )
    FFTRankingFactory(
        last_name=player2.last_name,
        first_name=player2.first_name,
        ranking=200,
        gender=Tournament.Gender.MALE,
    )
    pair = PairFactory(tournament=tournament, player1=player1, player2=player2, weight=None)

    client.get(url(tournament.pk))

    pair.refresh_from_db()
    assert pair.weight == 300.0


@pytest.mark.django_db
def test_weight_not_updated_when_only_one_has_ranking(client, tournament):
    player1 = PlayerFactory(ranking=None)
    player2 = PlayerFactory(ranking=None)
    FFTRankingFactory(
        last_name=player1.last_name,
        first_name=player1.first_name,
        ranking=100,
        gender=Tournament.Gender.MALE,
    )
    pair = PairFactory(tournament=tournament, player1=player1, player2=player2, weight=None)

    client.get(url(tournament.pk))

    pair.refresh_from_db()
    assert pair.weight is None


# ---------------------------------------------------------------------------
# Normalisation des noms (accents, tirets)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_hyphen_in_first_name_matches_space(client, tournament):
    """'paul-henri' (joueur) doit matcher 'paul henri' (FFT)."""
    player = PlayerFactory(ranking=None, first_name="paul-henri", last_name="argiot")
    FFTRankingFactory(
        last_name="argiot",
        first_name="paul henri",
        ranking=55,
        gender=Tournament.Gender.MALE,
    )
    partner = PlayerFactory(ranking=None)
    PairFactory(tournament=tournament, player1=player, player2=partner)

    client.get(url(tournament.pk))

    player.refresh_from_db()
    assert player.ranking == 55


@pytest.mark.django_db
def test_missing_accent_in_first_name_matches(client, tournament):
    """'Clement' (joueur sans accent) doit matcher 'Clément' (FFT avec accent)."""
    player = PlayerFactory(ranking=None, first_name="Clement", last_name="niot")
    FFTRankingFactory(
        last_name="niot",
        first_name="Clément",
        ranking=88,
        gender=Tournament.Gender.MALE,
    )
    partner = PlayerFactory(ranking=None)
    PairFactory(tournament=tournament, player1=player, player2=partner)

    client.get(url(tournament.pk))

    player.refresh_from_db()
    assert player.ranking == 88


# ---------------------------------------------------------------------------
# Format de réponse
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Non-écrasement du poids existant
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_existing_weight_not_overwritten_by_matching(client, tournament):
    """
    When a pair already has a weight set, match_and_update_rankings must NOT
    overwrite it — even if both players have rankings.
    """
    player1 = PlayerFactory(ranking=100)
    player2 = PlayerFactory(ranking=200)
    pair = PairFactory(tournament=tournament, player1=player1, player2=player2, weight=999.0)

    client.get(url(tournament.pk))

    pair.refresh_from_db()
    assert pair.weight == 999.0


@pytest.mark.django_db
def test_weight_computed_when_pair_weight_is_none_and_players_already_ranked(
    client, tournament
):
    """
    When a pair has weight=None and both players already have rankings
    (not from FFT matching), weight must be computed.
    """
    player1 = PlayerFactory(ranking=100)
    player2 = PlayerFactory(ranking=200)
    pair = PairFactory(tournament=tournament, player1=player1, player2=player2, weight=None)

    client.get(url(tournament.pk))

    pair.refresh_from_db()
    assert pair.weight == 300.0


# ---------------------------------------------------------------------------
# Transition de statut DRAFT → SET
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tournament_transitions_to_set_after_ranking_match():
    from apps.players.services.ranking_matching_service import match_and_update_rankings

    tournament = TournamentFactory(
        gender=Tournament.Gender.MALE,
        league=Tournament.League.ILE_DE_FRANCE,
        game_format=Tournament.GameFormat.B1,
        configuration=Tournament.Configuration.TMC,
    )
    players = [PlayerFactory(ranking=None) for _ in range(8)]
    for i, player in enumerate(players):
        FFTRankingFactory(
            last_name=player.last_name,
            first_name=player.first_name,
            ranking=100 + i * 50,
            gender=Tournament.Gender.MALE,
        )
    for i in range(0, 8, 2):
        PairFactory(tournament=tournament, player1=players[i], player2=players[i + 1], weight=None)

    match_and_update_rankings(tournament)

    tournament.refresh_from_db()
    assert tournament.status == Tournament.Status.SET


# ---------------------------------------------------------------------------
# Format de réponse
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_response_contains_pairs_with_players_and_weight(client, tournament):
    player1 = PlayerFactory(ranking=None)
    player2 = PlayerFactory(ranking=None)
    FFTRankingFactory(
        last_name=player1.last_name,
        first_name=player1.first_name,
        ranking=100,
        gender=Tournament.Gender.MALE,
    )
    FFTRankingFactory(
        last_name=player2.last_name,
        first_name=player2.first_name,
        ranking=200,
        gender=Tournament.Gender.MALE,
    )
    PairFactory(tournament=tournament, player1=player1, player2=player2, weight=None)

    response = client.get(url(tournament.pk))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    pair_data = response.data[0]
    assert "player1" in pair_data
    assert "player2" in pair_data
    assert "weight" in pair_data
    assert pair_data["weight"] == 300.0
    assert pair_data["player1"]["ranking"] == 100
    assert pair_data["player2"]["ranking"] == 200
