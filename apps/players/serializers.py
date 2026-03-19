from django.db import models as db_models
from rest_framework import serializers

from .models import Pair, Player
from .services.ranking_matching_service import fill_rankings_for_players


class PlayerInPairSerializer(serializers.ModelSerializer):
    # Remove the auto-generated UniqueValidator on license_number so that
    # we can handle upsert logic ourselves (update_or_create in PairSerializer).
    license_number = serializers.CharField(max_length=50)
    # allow_null=True: the FFT CSV export and some clients send null for an empty phone.
    # validate_phone normalises null → "" so the model CharField (non-nullable) is
    # never given None. default="" handles the field being absent from the payload.
    phone = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True, default="")

    class Meta:
        model = Player
        fields = ["id", "last_name", "first_name", "license_number", "phone", "ranking"]
        read_only_fields = ["id"]

    def validate_phone(self, value: str | None) -> str:
        # Coerce null (allowed by allow_null=True) to empty string.
        return value or ""


class PlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ["id", "last_name", "first_name", "license_number", "phone", "ranking"]
        read_only_fields = ["id"]


class PairSerializer(serializers.ModelSerializer):
    player1 = PlayerInPairSerializer()
    player2 = PlayerInPairSerializer()

    class Meta:
        model = Pair
        fields = ["id", "player1", "player2", "weight", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def _get_tournament(self):
        tournament = self.context.get("tournament")
        if tournament is None and self.instance:
            return self.instance.tournament
        return tournament

    def validate(self, data: dict) -> dict:
        player1_data = data.get("player1", {})
        player2_data = data.get("player2", {})

        p1_license = player1_data.get("license_number")
        p2_license = player2_data.get("license_number")

        if p1_license and p2_license and p1_license == p2_license:
            raise serializers.ValidationError(
                {"player2": ["Les deux joueurs doivent être différents."]}
            )

        tournament = self._get_tournament()
        if tournament and p1_license and p2_license:
            # Check player1 not already in tournament (exclude current pair on update)
            existing = Pair.objects.filter(tournament=tournament).filter(
                db_models.Q(player1__license_number=p1_license)
                | db_models.Q(player2__license_number=p1_license)
            )
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    {"player1": ["Ce joueur est déjà inscrit dans ce tournoi."]}
                )

            # Check player2 not already in tournament (exclude current pair on update)
            existing2 = Pair.objects.filter(tournament=tournament).filter(
                db_models.Q(player1__license_number=p2_license)
                | db_models.Q(player2__license_number=p2_license)
            )
            if self.instance:
                existing2 = existing2.exclude(pk=self.instance.pk)
            if existing2.exists():
                raise serializers.ValidationError(
                    {"player2": ["Ce joueur est déjà inscrit dans ce tournoi."]}
                )

        return data

    def _upsert_player(self, player_data: dict) -> Player:
        license_number = player_data.get("license_number")
        player, _ = Player.objects.update_or_create(
            license_number=license_number,
            defaults={k: v for k, v in player_data.items() if k != "license_number"},
        )
        return player

    @staticmethod
    def _compute_weight(player1: Player, player2: Player) -> float | None:
        """Return player1.ranking + player2.ranking, or None if either is missing."""
        if player1.ranking is not None and player2.ranking is not None:
            return float(player1.ranking + player2.ranking)
        return None

    def _fill_rankings(self, players: list[Player], force: bool = False) -> None:
        """Delegate FFT ranking lookup to the ranking service.

        See fill_rankings_for_players for the force=True semantics.
        """
        tournament = self._get_tournament()
        if tournament is None:
            return
        fill_rankings_for_players(players, tournament, force=force)

    def create(self, validated_data: dict) -> Pair:
        player1_data = validated_data.pop("player1")
        player2_data = validated_data.pop("player2")
        player1 = self._upsert_player(player1_data)
        player2 = self._upsert_player(player2_data)

        # force=True: the submitted payload fully defines the player's identity
        # (including last_name / first_name), so we always re-resolve their FFT
        # ranking — even if a ranking was already present before this request.
        # This is intentional: creating a pair is an explicit data entry action
        # and the FFT lookup is the authoritative source for the ranking.
        self._fill_rankings([player1, player2], force=True)

        calculated = self._compute_weight(player1, player2)
        if calculated is not None:
            validated_data["weight"] = calculated

        return Pair.objects.create(player1=player1, player2=player2, **validated_data)

    def update(self, instance: Pair, validated_data: dict) -> Pair:
        player1_data = validated_data.pop("player1", None)
        player2_data = validated_data.pop("player2", None)

        if player1_data:
            self._update_player(instance.player1, player1_data)
        if player2_data:
            self._update_player(instance.player2, player2_data)

        instance.player1.refresh_from_db()
        instance.player2.refresh_from_db()
        updated_players = []
        if player1_data:
            updated_players.append(instance.player1)
        if player2_data:
            updated_players.append(instance.player2)
        updated_pks = {p.pk for p in updated_players}
        unchanged_players = [
            p for p in [instance.player1, instance.player2] if p.pk not in updated_pks
        ]
        # force=True on updated players: any field change (including last_name /
        # first_name) may have altered their identity, so we re-resolve their FFT
        # ranking unconditionally. Players whose data was NOT touched in this
        # request are passed with force=False so manually-set rankings are kept.
        self._fill_rankings(updated_players, force=True)
        self._fill_rankings(unchanged_players, force=False)
        should_recalculate = bool(updated_players) or instance.weight is None
        if should_recalculate:
            calculated = self._compute_weight(instance.player1, instance.player2)
            if calculated is not None:
                validated_data["weight"] = calculated

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    def _update_player(self, player: Player, data: dict) -> None:
        for attr, value in data.items():
            setattr(player, attr, value)
        player.save()


class PairCSVImportSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        if not value.name.endswith(".csv"):
            raise serializers.ValidationError("Le fichier doit être au format CSV (.csv).")
        return value
