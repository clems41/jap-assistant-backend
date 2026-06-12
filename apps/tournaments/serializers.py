from rest_framework import serializers

from apps.tournaments.models import TimeSlot, Tournament


class TournamentSerializer(serializers.ModelSerializer):
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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "status", "pairs_count", "created_at", "updated_at"]


class LastInformationSerializer(serializers.Serializer):
    league = serializers.CharField(allow_null=True)
    location = serializers.CharField(allow_null=True)


class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = ["id", "tournament", "start_time", "end_time", "courts_available", "created_at", "updated_at"]
        read_only_fields = ["id", "tournament", "created_at", "updated_at"]

    def validate(self, attrs: dict) -> dict:
        start = attrs.get("start_time")
        end = attrs.get("end_time")
        if start is not None and end is not None and end <= start:
            raise serializers.ValidationError(
                {"end_time": ["L'heure de fin doit être postérieure à l'heure de début."]}
            )
        return attrs

    def validate_courts_available(self, value: int) -> int:
        if value < 1:
            raise serializers.ValidationError(
                "Le nombre de courts doit être supérieur ou égal à 1."
            )
        return value
