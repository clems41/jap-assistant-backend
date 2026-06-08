from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.players.models import Pair

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
            "winner_id",
            "game_format",
            "score",
            "child1",
            "child2",
        ]
        read_only_fields = ["id", "round", "round_display", "match_number", "pair1", "pair2", "game_format", "child1", "child2"]

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


class MatchScoreSerializer(serializers.Serializer):
    score = serializers.CharField(max_length=50)
    winner_id = serializers.IntegerField()

    def validate(self, attrs: dict) -> dict:
        match: Match = self.context["match"]

        if match.pair1_id is None and match.pair2_id is None:
            raise serializers.ValidationError(
                ["Les paires du match ne sont pas encore définies."]
            )

        winner_id: int = attrs["winner_id"]
        if winner_id not in (match.pair1_id, match.pair2_id):
            raise serializers.ValidationError(
                {
                    "winner_id": [
                        "Le vainqueur doit être l'une des deux paires du match."
                    ]
                }
            )

        return attrs


class MatchPlacementItemSerializer(serializers.Serializer):
    match_id = serializers.IntegerField()
    pair1_id = serializers.IntegerField(allow_null=True)
    pair2_id = serializers.IntegerField(allow_null=True)


class BracketPlacementSerializer(serializers.Serializer):
    placements = MatchPlacementItemSerializer(many=True)

    def validate(self, attrs: dict) -> dict:
        bracket: Bracket = self.context["bracket"]
        tournament = self.context["tournament"]
        placements: list[dict] = attrs["placements"]
        requested_match_ids = {p["match_id"] for p in placements}

        matches_map = {
            m.pk: m
            for m in Match.objects.filter(bracket=bracket, pk__in=requested_match_ids)
        }

        pair_ids_in_request: list[int] = []
        for p in placements:
            match = matches_map.get(p["match_id"])
            if match is None:
                raise serializers.ValidationError(
                    {"match_id": [f"Le match {p['match_id']} n'appartient pas à ce tableau."]}
                )
            if match.score:
                raise serializers.ValidationError(
                    {"match_id": [f"Le match {p['match_id']} a déjà un score enregistré."]}
                )
            if p["pair1_id"] is not None and p["pair1_id"] == p["pair2_id"]:
                raise serializers.ValidationError(
                    ["Une paire ne peut pas être placée deux fois dans le même match."]
                )
            for pair_id in (p["pair1_id"], p["pair2_id"]):
                if pair_id is not None:
                    pair_ids_in_request.append(pair_id)

        if pair_ids_in_request:
            valid_pair_ids = set(
                Pair.objects.filter(
                    pk__in=pair_ids_in_request, tournament=tournament
                ).values_list("pk", flat=True)
            )
            for pid in pair_ids_in_request:
                if pid not in valid_pair_ids:
                    raise serializers.ValidationError(
                        {"pair_id": [f"La paire {pid} n'appartient pas à ce tournoi."]}
                    )

        if len(pair_ids_in_request) != len(set(pair_ids_in_request)):
            raise serializers.ValidationError(
                ["Une paire ne peut être placée qu'une seule fois dans le tableau."]
            )

        existing_pair_ids: set[int] = set()
        for m in Match.objects.filter(bracket=bracket).exclude(pk__in=requested_match_ids):
            if m.pair1_id:
                existing_pair_ids.add(m.pair1_id)
            if m.pair2_id:
                existing_pair_ids.add(m.pair2_id)

        overlap = set(pair_ids_in_request) & existing_pair_ids
        if overlap:
            raise serializers.ValidationError(
                ["Une paire ne peut être placée qu'une seule fois dans le tableau."]
            )

        attrs["_matches"] = matches_map
        return attrs


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
