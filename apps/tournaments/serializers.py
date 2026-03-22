from rest_framework import serializers

from apps.tournaments.models import Tournament


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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]


class LastLeagueSerializer(serializers.Serializer):
    league = serializers.CharField(allow_null=True)
