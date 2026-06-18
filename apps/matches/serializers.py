from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.players.models import Pair

from .models import Bracket, Match, Round


class MatchSerializer(serializers.ModelSerializer):
    round_display = serializers.CharField(source="get_display_round", read_only=True)
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
            "disabled",
            "pair1_can_be_placed",
            "pair2_can_be_placed",
        ]
        read_only_fields = [
            "id",
            "round",
            "round_display",
            "match_number",
            "pair1",
            "pair2",
            "game_format",
            "child1",
            "child2",
            "disabled",
            "pair1_can_be_placed",
            "pair2_can_be_placed",
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
MatchSerializer.get_child1 = extend_schema_field(MatchSerializer)(
    MatchSerializer.get_child1
)
MatchSerializer.get_child2 = extend_schema_field(MatchSerializer)(
    MatchSerializer.get_child2
)


class ClassificationBracketSerializer(serializers.ModelSerializer):
    source_round_display = serializers.CharField(
        source="get_display_source_round", read_only=True
    )
    root_match = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = Bracket
        fields = [
            "id",
            "dimension",
            "source_round",
            "source_round_display",
            "start_place",
            "end_place",
            "root_match",
            "children",
        ]

    def get_root_match(self, obj: Bracket) -> dict:
        root = obj.matches.get(round=Round.FINALE)
        return MatchSerializer(root).data

    def get_children(self, obj: Bracket) -> list[dict]:
        children = obj.children.all().order_by("-start_place")
        return ClassificationBracketSerializer(children, many=True).data


# Applied after class definition to resolve the self-referential forward
# reference, same pattern as MatchSerializer.get_child1/get_child2.
ClassificationBracketSerializer.get_root_match = extend_schema_field(MatchSerializer)(
    ClassificationBracketSerializer.get_root_match
)
ClassificationBracketSerializer.get_children = extend_schema_field(
    ClassificationBracketSerializer
)(ClassificationBracketSerializer.get_children)


class BracketSerializer(serializers.ModelSerializer):
    root_match = serializers.SerializerMethodField()
    classification_brackets = serializers.SerializerMethodField()

    class Meta:
        model = Bracket
        fields = [
            "id",
            "dimension",
            "nb_pair_round_64",
            "nb_pair_round_32",
            "nb_pair_round_16",
            "nb_pair_round_8",
            "nb_pair_round_4",
            "root_match",
            "classification_brackets",
        ]

    @extend_schema_field(MatchSerializer)
    def get_root_match(self, obj: Bracket) -> dict:
        root = obj.matches.get(round=Round.FINALE)
        return MatchSerializer(root).data

    @extend_schema_field(ClassificationBracketSerializer)
    def get_classification_brackets(self, obj: Bracket) -> list[dict]:
        children = obj.children.all().order_by("-start_place")
        return ClassificationBracketSerializer(children, many=True).data


class MatchScoreSerializer(serializers.Serializer):
    score = serializers.CharField(max_length=50)
    winner_id = serializers.IntegerField()

    def validate(self, attrs: dict) -> dict:
        match: Match = self.context["match"]

        if match.disabled:
            raise serializers.ValidationError(
                ["Ce match est désactivé et ne peut pas être joué."]
            )

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
                    {
                        "match_id": [
                            f"Le match {p['match_id']} n'appartient pas à ce tableau."
                        ]
                    }
                )
            if match.score:
                raise serializers.ValidationError(
                    {
                        "match_id": [
                            f"Le match {p['match_id']} a déjà un score enregistré."
                        ]
                    }
                )
            placing_into_pair1 = (
                p["pair1_id"] is not None and p["pair1_id"] != match.pair1_id
            )
            placing_into_pair2 = (
                p["pair2_id"] is not None and p["pair2_id"] != match.pair2_id
            )
            if (placing_into_pair1 or placing_into_pair2) and match.disabled:
                raise serializers.ValidationError(
                    {"match_id": [f"Le match {p['match_id']} est désactivé."]}
                )
            if placing_into_pair1 and not match.pair1_can_be_placed:
                raise serializers.ValidationError(
                    {
                        "pair1_id": [
                            f"Aucune paire ne peut être placée dans cet emplacement "
                            f"du match {p['match_id']}."
                        ]
                    }
                )
            if placing_into_pair2 and not match.pair2_can_be_placed:
                raise serializers.ValidationError(
                    {
                        "pair2_id": [
                            f"Aucune paire ne peut être placée dans cet emplacement "
                            f"du match {p['match_id']}."
                        ]
                    }
                )
            if p["pair1_id"] is not None and p["pair1_id"] == p["pair2_id"]:
                raise serializers.ValidationError(
                    ["Une paire ne peut pas être placée deux fois dans le même match."]
                )
            if placing_into_pair1:
                pair_ids_in_request.append(p["pair1_id"])
            if placing_into_pair2:
                pair_ids_in_request.append(p["pair2_id"])

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
        for m in Match.objects.filter(bracket=bracket).exclude(
            pk__in=requested_match_ids
        ):
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

    ROUND_FIELDS = [
        "nb_pair_round_64",
        "nb_pair_round_32",
        "nb_pair_round_16",
        "nb_pair_round_8",
        "nb_pair_round_4",
    ]
    ROUND_SIZE_BY_FIELD = {
        "nb_pair_round_64": 64,
        "nb_pair_round_32": 32,
        "nb_pair_round_16": 16,
        "nb_pair_round_8": 8,
        "nb_pair_round_4": 4,
    }

    MIN_VALUE_ERROR_MESSAGE = (
        "Assurez-vous que cette valeur est supérieure ou égale à 0."
    )

    dimension = serializers.IntegerField()
    nb_pair_round_64 = serializers.IntegerField(
        min_value=0, error_messages={"min_value": MIN_VALUE_ERROR_MESSAGE}
    )
    nb_pair_round_32 = serializers.IntegerField(
        min_value=0, error_messages={"min_value": MIN_VALUE_ERROR_MESSAGE}
    )
    nb_pair_round_16 = serializers.IntegerField(
        min_value=0, error_messages={"min_value": MIN_VALUE_ERROR_MESSAGE}
    )
    nb_pair_round_8 = serializers.IntegerField(
        min_value=0, error_messages={"min_value": MIN_VALUE_ERROR_MESSAGE}
    )
    nb_pair_round_4 = serializers.IntegerField(
        min_value=0, error_messages={"min_value": MIN_VALUE_ERROR_MESSAGE}
    )

    def validate_dimension(self, value: int) -> int:
        if value not in self.VALID_DIMENSIONS:
            raise serializers.ValidationError(
                f"La dimension doit être l'une des valeurs suivantes : {sorted(self.VALID_DIMENSIONS)}."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        dimension = attrs.get("dimension")
        if dimension is None:
            return attrs

        pair_count = self.context["tournament"].pairs_count

        field_errors: dict[str, list[str]] = {}
        remaining = pair_count
        for field_name in self.ROUND_FIELDS:
            value = attrs.get(field_name)
            if value is None:
                continue
            round_size = self.ROUND_SIZE_BY_FIELD[field_name]

            if round_size > dimension and value != 0:
                field_errors[field_name] = [
                    f"Ce champ doit être à 0 : le tour correspondant n'existe pas "
                    f"pour une dimension {dimension}."
                ]
                continue
            if value > remaining:
                field_errors[field_name] = [
                    f"Cette valeur ne peut pas dépasser {remaining} (paires restantes)."
                ]
            remaining -= value

        if field_errors:
            raise serializers.ValidationError(field_errors)

        total = sum(attrs[f] for f in self.ROUND_FIELDS)
        if total != pair_count:
            raise serializers.ValidationError(
                [
                    f"La somme des paires placées par tour ({total}) doit être égale "
                    f"au nombre de paires inscrites au tournoi ({pair_count})."
                ]
            )

        self._validate_structural_capacity(attrs, dimension)
        return attrs

    def _validate_structural_capacity(self, attrs: dict, dimension: int) -> None:
        """Simulate Step A of the classification-bracket generation algorithm
        to detect, ahead of time, any nb_pair_round_X configuration that is
        structurally inconsistent round by round (entering must be even, and
        real_matches must not exceed the structural cap of that round).
        """
        applicable_fields = [
            field_name
            for field_name in self.ROUND_FIELDS
            if self.ROUND_SIZE_BY_FIELD[field_name] <= dimension
        ]

        carried_winners = 0
        for index, field_name in enumerate(applicable_fields):
            new_entrants = attrs[field_name]
            entering = carried_winners + new_entrants
            real_matches = entering // 2
            structural_cap = dimension // (2 ** (index + 1))

            if entering % 2 != 0 or real_matches > structural_cap:
                round_size = self.ROUND_SIZE_BY_FIELD[field_name]
                raise serializers.ValidationError(
                    [
                        f"La répartition des paires par tour n'est pas cohérente : "
                        f"le tour {round_size} ne peut pas accueillir plus de "
                        f"{structural_cap} matchs réels."
                    ]
                )
            carried_winners = real_matches
