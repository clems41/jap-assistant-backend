from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Bracket, Match, Round


class MatchSerializer(serializers.ModelSerializer):
    round_display = serializers.CharField(source="get_round_display", read_only=True)
    child1 = serializers.SerializerMethodField()
    child2 = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            "id",
            "round",
            "round_display",
            "match_number",
            "pair1",
            "pair2",
            "game_format",
            "score",
            "child1",
            "child2",
        ]

    def get_child1(self, obj: Match) -> dict | None:
        if obj.child1_id is None:
            return None
        child = obj.child1 if hasattr(obj, "_child1_cache") else obj.child1
        return MatchSerializer(child).data

    def get_child2(self, obj: Match) -> dict | None:
        if obj.child2_id is None:
            return None
        child = obj.child2 if hasattr(obj, "_child2_cache") else obj.child2
        return MatchSerializer(child).data


# Applied after class definition to resolve the self-referential forward reference.
MatchSerializer.get_child1 = extend_schema_field(MatchSerializer)(MatchSerializer.get_child1)
MatchSerializer.get_child2 = extend_schema_field(MatchSerializer)(MatchSerializer.get_child2)


class BracketSerializer(serializers.ModelSerializer):
    root_match = serializers.SerializerMethodField()

    class Meta:
        model = Bracket
        fields = ["id", "dimension", "nb_top_seeds", "root_match"]

    @extend_schema_field(MatchSerializer)
    def get_root_match(self, obj: Bracket) -> dict:
        root = obj.matches.get(round=Round.FINALE)
        return MatchSerializer(root).data


class BracketGenerateSerializer(serializers.Serializer):
    VALID_DIMENSIONS = {8, 16, 32, 64}

    dimension = serializers.IntegerField()
    nb_top_seeds = serializers.IntegerField()

    def validate_dimension(self, value: int) -> int:
        if value not in self.VALID_DIMENSIONS:
            raise serializers.ValidationError(
                f"La dimension doit être l'une des valeurs suivantes : {sorted(self.VALID_DIMENSIONS)}."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        dimension = attrs.get("dimension")
        nb_top_seeds = attrs.get("nb_top_seeds")

        if dimension is None or nb_top_seeds is None:
            return attrs

        min_seeds = dimension // 8
        max_seeds = dimension // 2

        if not (min_seeds <= nb_top_seeds <= max_seeds):
            raise serializers.ValidationError(
                {
                    "nb_top_seeds": (
                        f"Le nombre de têtes de série doit être compris entre "
                        f"{min_seeds} et {max_seeds} pour une dimension {dimension}."
                    )
                }
            )

        return attrs
