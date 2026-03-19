import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.players.models import Pair, Player
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
