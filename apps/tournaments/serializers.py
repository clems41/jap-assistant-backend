from django.conf import settings
from rest_framework import serializers

from apps.tournaments.models import TimeSlot, Tournament


class TournamentSerializer(serializers.ModelSerializer):
    qr_code_url = serializers.SerializerMethodField()

    class Meta:
        model = Tournament
        fields = [
            "id",
            "owner",
            "name",
            "category",
            "start_date",
            "location",
            "league",
            "gender",
            "game_format",
            "configuration",
            "estimated_match_duration",
            "status",
            "pairs_count",
            "qr_code_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner",
            "status",
            "pairs_count",
            "qr_code_url",
            "created_at",
            "updated_at",
        ]

    def get_qr_code_url(self, obj: Tournament) -> str:
        return f"{settings.FRONTEND_URL}/public/tournaments/{obj.public_code}"


class PublicTournamentSerializer(serializers.ModelSerializer):
    """Read-only, unauthenticated view of a tournament, exposed via its
    public_code instead of the internal numeric id."""

    class Meta:
        model = Tournament
        fields = [
            "public_code",
            "name",
            "category",
            "start_date",
            "location",
            "league",
            "gender",
            "game_format",
            "configuration",
            "estimated_match_duration",
            "status",
            "pairs_count",
        ]
        read_only_fields = fields


class InformationsSerializer(serializers.Serializer):
    last_league = serializers.CharField(allow_null=True)
    last_location = serializers.CharField(allow_null=True)
    all_locations = serializers.ListField(child=serializers.CharField())


class SetStatusPairWithoutWeightSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    player1 = serializers.CharField()
    player2 = serializers.CharField()


class SetStatusPlayerWithoutRankingSerializer(serializers.Serializer):
    pair_id = serializers.IntegerField()
    player_id = serializers.IntegerField()
    full_name = serializers.CharField()


class TournamentSetReadinessSerializer(serializers.Serializer):
    is_set_ready = serializers.BooleanField()
    missing_configuration = serializers.BooleanField()
    missing_game_format = serializers.BooleanField()
    pairs_count = serializers.IntegerField()
    pairs_without_weight = SetStatusPairWithoutWeightSerializer(many=True)
    players_without_ranking = SetStatusPlayerWithoutRankingSerializer(many=True)


class TournamentRecomputeStatusSerializer(serializers.Serializer):
    status_before = serializers.CharField()
    status_after = serializers.CharField()


class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = [
            "id",
            "tournament",
            "start_time",
            "end_time",
            "courts_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tournament", "created_at", "updated_at"]

    def validate(self, attrs: dict) -> dict:
        start = attrs.get("start_time")
        end = attrs.get("end_time")
        if start is not None and end is not None and end <= start:
            raise serializers.ValidationError(
                {
                    "end_time": [
                        "L'heure de fin doit être postérieure à l'heure de début."
                    ]
                }
            )
        return attrs

    def validate_courts_available(self, value: int) -> int:
        if value < 1:
            raise serializers.ValidationError(
                "Le nombre de courts doit être supérieur ou égal à 1."
            )
        return value
