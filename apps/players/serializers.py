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

    @staticmethod
    def _ranking_changed(player_data: dict, original_ranking: int | None) -> bool:
        """Return True if the payload contains a 'ranking' value that differs from the DB.

        A ranking is considered an intentional override only when its value
        actually changes.  This distinction matters for PUT requests where all
        fields are always present in the payload — a ranking key whose value
        matches the DB is NOT an explicit override.
        """
        if "ranking" not in player_data:
            return False
        return player_data["ranking"] != original_ranking

    @staticmethod
    def _name_changed(
        player_data: dict, original_last: str, original_first: str
    ) -> bool:
        """Return True if last_name or first_name differs from the original DB values."""
        return (
            player_data.get("last_name", original_last) != original_last
            or player_data.get("first_name", original_first) != original_first
        )

    def update(self, instance: Pair, validated_data: dict) -> Pair:
        player1_data = validated_data.pop("player1", None)
        player2_data = validated_data.pop("player2", None)

        # Snapshot names AND rankings BEFORE updating so we can detect changes below.
        p1_original_last = instance.player1.last_name
        p1_original_first = instance.player1.first_name
        p1_original_ranking = instance.player1.ranking
        p2_original_last = instance.player2.last_name
        p2_original_first = instance.player2.first_name
        p2_original_ranking = instance.player2.ranking

        if player1_data:
            self._update_player(instance.player1, player1_data)
        if player2_data:
            self._update_player(instance.player2, player2_data)

        instance.player1.refresh_from_db()
        instance.player2.refresh_from_db()

        # Classify each updated player into one of three buckets:
        #   - ranking_explicit: caller sent a ranking value that DIFFERS from the
        #                       current DB value → skip FFT entirely (intentional change)
        #   - name_changed:     name changed without explicit ranking change → force=True
        #   - soft_update:      other fields only → force=False
        #
        # Note: with PUT all fields are always present in the payload.  Checking
        # only for the presence of the "ranking" key (old logic) would incorrectly
        # mark an unchanged ranking as explicit, preventing the FFT re-fetch when
        # the name changes.  Comparing the value against the DB snapshot is the
        # only reliable way to detect an intentional ranking override.
        ranking_explicit_players: list[Player] = []
        force_players: list[Player] = []
        soft_players: list[Player] = []
        unchanged_players: list[Player] = []

        originals = {
            instance.player1.pk: (p1_original_last, p1_original_first, p1_original_ranking),
            instance.player2.pk: (p2_original_last, p2_original_first, p2_original_ranking),
        }

        for player, player_data in [
            (instance.player1, player1_data),
            (instance.player2, player2_data),
        ]:
            orig_last, orig_first, orig_ranking = originals[player.pk]
            if player_data is None:
                unchanged_players.append(player)
            elif self._ranking_changed(player_data, orig_ranking):
                ranking_explicit_players.append(player)
            elif self._name_changed(player_data, orig_last, orig_first):
                force_players.append(player)
            else:
                soft_players.append(player)

        # Players with explicit ranking: already saved via _update_player, no FFT.
        # Players with name change: re-fetch FFT (may overwrite old stale ranking).
        # Players with soft update or no update: keep existing ranking.
        self._fill_rankings(force_players, force=True)
        self._fill_rankings(soft_players + unchanged_players, force=False)

        should_recalculate = bool(player1_data or player2_data) or instance.weight is None
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
