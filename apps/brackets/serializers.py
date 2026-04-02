from rest_framework import serializers

from apps.players.models import Pair

from .models import BracketSlot, BracketState, DIMENSION_CHOICES

# ---------------------------------------------------------------------------
# Read serializers (GET response)
# ---------------------------------------------------------------------------


class PlayerInBracketSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    last_name = serializers.CharField()
    first_name = serializers.CharField()
    license_number = serializers.CharField()
    ranking = serializers.IntegerField(allow_null=True)


class PairInBracketSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    player1 = PlayerInBracketSerializer()
    player2 = PlayerInBracketSerializer()
    weight = serializers.FloatField(allow_null=True)


class BracketSlotReadSerializer(serializers.ModelSerializer):
    pair = PairInBracketSerializer()

    class Meta:
        model = BracketSlot
        fields = ["slot_title", "pair"]


class BracketStateSerializer(serializers.ModelSerializer):
    tournament_id = serializers.IntegerField(source="tournament.pk")
    slots = BracketSlotReadSerializer(many=True)

    class Meta:
        model = BracketState
        fields = ["id", "tournament_id", "dimension", "nb_top_seeds", "slots"]


# ---------------------------------------------------------------------------
# Write serializers (PUT request)
# ---------------------------------------------------------------------------

VALID_DIMENSIONS = {v for v, _ in DIMENSION_CHOICES}


class BracketSlotWriteSerializer(serializers.Serializer):
    slot_title = serializers.CharField(max_length=20)
    pair_id = serializers.IntegerField()


class BracketStateWriteSerializer(serializers.Serializer):
    dimension = serializers.IntegerField()
    nb_top_seeds = serializers.IntegerField(min_value=0)
    slots = BracketSlotWriteSerializer(many=True)

    def validate_dimension(self, value: int) -> int:
        if value not in VALID_DIMENSIONS:
            raise serializers.ValidationError(
                f"La dimension doit être l'une des valeurs suivantes : {sorted(VALID_DIMENSIONS)}."
            )
        return value

    def validate_slots(self, slots: list) -> list:
        pair_ids = [s["pair_id"] for s in slots]
        slot_titles = [s["slot_title"] for s in slots]

        if len(pair_ids) != len(set(pair_ids)):
            raise serializers.ValidationError(
                "Une même paire ne peut pas apparaître plusieurs fois dans le tableau."
            )
        if len(slot_titles) != len(set(slot_titles)):
            raise serializers.ValidationError(
                "Un même slot ne peut pas contenir plusieurs paires."
            )
        return slots

    def validate(self, attrs: dict) -> dict:
        slots = attrs.get("slots", [])
        if not slots:
            return attrs

        tournament = self.context["tournament"]
        pair_ids = [s["pair_id"] for s in slots]
        valid_ids = set(
            Pair.objects.filter(tournament=tournament, pk__in=pair_ids).values_list(
                "pk", flat=True
            )
        )
        invalid = set(pair_ids) - valid_ids
        if invalid:
            raise serializers.ValidationError(
                {
                    "slots": (
                        f"Les paires suivantes n'appartiennent pas à ce tournoi : {sorted(invalid)}."
                    )
                }
            )
        return attrs
