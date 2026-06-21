from django.db import models

from apps.common.models import TimeStampedModel
from apps.tournaments.models import Tournament


class Round(models.TextChoices):
    FINALE = "FINALE", "Finale"
    DEMIE_FINALE = "DEMIE_FINALE", "Demies"
    QUART_DE_FINALE = "QUART_DE_FINALE", "Quarts"
    HUITIEME_DE_FINALE = "HUITIEME_DE_FINALE", "Huitièmes"
    SEIZIEME_DE_FINALE = "SEIZIEME_DE_FINALE", "Seizièmes"
    TRENTE_DEUXIEME_DE_FINALE = "TRENTE_DEUXIEME_DE_FINALE", "32èmes"


ROUNDS_BY_DIMENSION: dict[int, list[str]] = {
    2: [
        Round.FINALE,
    ],
    4: [
        Round.DEMIE_FINALE,
        Round.FINALE,
    ],
    8: [
        Round.QUART_DE_FINALE,
        Round.DEMIE_FINALE,
        Round.FINALE,
    ],
    16: [
        Round.HUITIEME_DE_FINALE,
        Round.QUART_DE_FINALE,
        Round.DEMIE_FINALE,
        Round.FINALE,
    ],
    32: [
        Round.SEIZIEME_DE_FINALE,
        Round.HUITIEME_DE_FINALE,
        Round.QUART_DE_FINALE,
        Round.DEMIE_FINALE,
        Round.FINALE,
    ],
    64: [
        Round.TRENTE_DEUXIEME_DE_FINALE,
        Round.SEIZIEME_DE_FINALE,
        Round.HUITIEME_DE_FINALE,
        Round.QUART_DE_FINALE,
        Round.DEMIE_FINALE,
        Round.FINALE,
    ],
}

ROUND_BY_SIZE: dict[int, str] = {
    64: Round.TRENTE_DEUXIEME_DE_FINALE,
    32: Round.SEIZIEME_DE_FINALE,
    16: Round.HUITIEME_DE_FINALE,
    8: Round.QUART_DE_FINALE,
    4: Round.DEMIE_FINALE,
}


def _place_range_label(start_place: int, dimension: int, round_name: str) -> str:
    """Return the "Places X-Y" label for `round_name` within a classification
    bracket of `dimension` starting at `start_place`.

    Shared by `Match.get_display_round()` (applied to a match's own bracket)
    and `Bracket.get_display_source_round()` (applied to a classification
    bracket's parent, when that parent is itself a classification bracket).
    """
    rounds = ROUNDS_BY_DIMENSION[dimension]
    round_index = rounds.index(round_name)
    end_place = start_place + dimension // (2**round_index) - 1
    return f"Places {start_place}-{end_place}"


class Bracket(TimeStampedModel):
    DIMENSION_CHOICES = [
        (2, "2"),
        (4, "4"),
        (8, "8"),
        (16, "16"),
        (32, "32"),
        (64, "64"),
    ]

    tournament = models.ForeignKey(
        Tournament,
        on_delete=models.CASCADE,
        related_name="brackets",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    source_round = models.CharField(
        max_length=30, choices=Round.choices, blank=True, default=""
    )
    start_place = models.PositiveSmallIntegerField(null=True, blank=True)
    end_place = models.PositiveSmallIntegerField(null=True, blank=True)
    dimension = models.PositiveSmallIntegerField(choices=DIMENSION_CHOICES)
    nb_pair_round_64 = models.PositiveSmallIntegerField(default=0)
    nb_pair_round_32 = models.PositiveSmallIntegerField(default=0)
    nb_pair_round_16 = models.PositiveSmallIntegerField(default=0)
    nb_pair_round_8 = models.PositiveSmallIntegerField(default=0)
    nb_pair_round_4 = models.PositiveSmallIntegerField(default=0)

    def __str__(self) -> str:
        return f"Bracket {self.dimension} — {self.tournament}"

    def get_display_source_round(self) -> str:
        """Return the user-facing label for `source_round`.

        `source_round` names the round of `self.parent` whose losers
        cascade into this classification bracket. When the parent is the
        main bracket, the generic Round label ("Seizièmes", "Quarts"...)
        is correct and used as-is. When the parent is itself a
        classification bracket (cascade of depth 2+), that round is
        displayed on the parent's matches as a "Places X-Y" label (see
        `Match.get_display_round()`), so `source_round_display` must match
        it instead of falling back to the generic label.
        """
        if self.parent is None or self.parent.start_place is None:
            return self.get_source_round_display()

        return _place_range_label(
            self.parent.start_place, self.parent.dimension, self.source_round
        )

    def recompute_placement_flags(self) -> None:
        """Recompute and persist disabled / pair{1,2}_can_be_placed for every
        match in this bracket.

        Stateless derived-state recompute, following the same pattern as
        Tournament.recompute_status(): rather than tracking how a slot was
        filled (direct placement vs winner propagation), the whole tree is
        walked from scratch each time the placement endpoint is called.

        Pass 1 (top-down from the root): a match is `disabled` if its parent
        is disabled, or if the parent's slot pointing to this match is filled
        with a pair that isn't this match's actual winner (i.e. a bypass
        placement skipping over this match).

        Pass 2 (after pass 1): a slot can no longer be placed into if the
        match is disabled, or if the corresponding child subtree already has
        a placement anywhere in it — unless overridden by the structural
        constraint (see `_compute_forced_sides`), which forces a single side
        regardless of placements.
        """
        matches = list(self.matches.all())
        by_id = {m.pk: m for m in matches}
        root = next(m for m in matches if m.round == Round.FINALE)

        self._compute_disabled(root, by_id)
        forced_side = self._compute_forced_sides(self, matches, by_id)
        for match in matches:
            match.pair1_can_be_placed = self._compute_can_be_placed(
                match, by_id.get(match.child1_id), by_id, forced_side, "pair1"
            )
            match.pair2_can_be_placed = self._compute_can_be_placed(
                match, by_id.get(match.child2_id), by_id, forced_side, "pair2"
            )

        Match.objects.bulk_update(
            matches, ["disabled", "pair1_can_be_placed", "pair2_can_be_placed"]
        )

    @staticmethod
    def _compute_disabled(node: "Match", by_id: dict[int, "Match"]) -> None:
        """Recursively set `disabled` top-down, starting from the root."""
        for child_id, parent_slot_pair_id in (
            (node.child1_id, node.pair1_id),
            (node.child2_id, node.pair2_id),
        ):
            child = by_id.get(child_id)
            if child is None:
                continue
            child.disabled = node.disabled or (
                parent_slot_pair_id is not None
                and parent_slot_pair_id != child.winner_id
            )
            Bracket._compute_disabled(child, by_id)

    @staticmethod
    def _compute_forced_sides(
        bracket: "Bracket", matches: list["Match"], by_id: dict[int, "Match"]
    ) -> dict[int, str]:
        """For every round other than the "premier tour" (the largest round
        size with a nonzero nb_pair_round_X), force which slot(s) may accept a
        placement, derived purely from nb_pair_round_X, independent of any
        actual placement:

        - nb_pair_round_X == 0: no pair is ever meant to enter this round
          directly, so neither slot may accept a placement ("locked") on any
          currently active match in it.
        - nb_pair_round_X == N (N = current count of active matches in the
          round): the round is fully saturated by direct entrants, so each
          active match accepts a placement on exactly one side (pair1 for the
          demi-finale #1 half, pair2 for the demi-finale #2 half), and the
          opposite child's entire subtree is force-disabled.
        - nb_pair_round_X not in {0, N}: current/unconstrained behavior.

        Does nothing at all if no round has any nonzero nb_pair_round_X
        (nothing to anchor a "premier tour" against).

        Processed smallest round size to largest (excluding the premier tour)
        since a round's force-disables must be finalized before computing the
        active-match count of the next, larger round.
        """
        rounds = ROUNDS_BY_DIMENSION[bracket.dimension]
        entrant_sizes = sorted(
            size
            for size in ROUND_BY_SIZE
            if size <= bracket.dimension
            and getattr(bracket, f"nb_pair_round_{size}") > 0
        )
        if not entrant_sizes:
            return {}
        premier_tour = entrant_sizes[-1]

        matches_by_round: dict[str, list[Match]] = {}
        for m in matches:
            matches_by_round.setdefault(m.round, []).append(m)

        forced_side: dict[int, str] = {}
        for size in sorted(s for s in ROUND_BY_SIZE if s <= bracket.dimension):
            if size == premier_tour:
                continue

            round_name = ROUND_BY_SIZE[size]
            round_index = rounds.index(round_name)
            num_matches = bracket.dimension // (2 ** (round_index + 1))
            half = num_matches // 2

            round_matches = sorted(
                matches_by_round.get(round_name, []), key=lambda m: m.match_number
            )
            active = [m for m in round_matches if not m.disabled]
            nb_pair = getattr(bracket, f"nb_pair_round_{size}")

            if nb_pair == 0:
                for m in active:
                    forced_side[m.pk] = "locked"
                continue

            if nb_pair != len(active):
                continue

            for m in active:
                if m.match_number <= half:
                    forced_side[m.pk] = "pair1"
                    Bracket._force_disable_subtree(by_id.get(m.child1_id), by_id)
                else:
                    forced_side[m.pk] = "pair2"
                    Bracket._force_disable_subtree(by_id.get(m.child2_id), by_id)

        return forced_side

    @staticmethod
    def _force_disable_subtree(node: "Match | None", by_id: dict[int, "Match"]) -> None:
        """Unconditionally disable `node` and its entire descendant subtree.

        Unlike `_compute_disabled` (which only disables a child when the
        parent's slot was bypassed by a real placement), this is a pure
        structural cascade: the subtree is disabled regardless of whether
        any placement exists in it.
        """
        if node is None:
            return
        node.disabled = True
        Bracket._force_disable_subtree(by_id.get(node.child1_id), by_id)
        Bracket._force_disable_subtree(by_id.get(node.child2_id), by_id)

    @staticmethod
    def _compute_can_be_placed(
        match: "Match",
        child: "Match | None",
        by_id: dict[int, "Match"],
        forced_side: dict[int, str],
        slot: str,
    ) -> bool:
        if match.disabled:
            return False
        if match.pk in forced_side:
            return forced_side[match.pk] == slot
        return not Bracket._has_placement(child, by_id)

    @staticmethod
    def _has_placement(node: "Match | None", by_id: dict[int, "Match"]) -> bool:
        if node is None:
            return False
        return (
            node.pair1_id is not None
            or node.pair2_id is not None
            or Bracket._has_placement(by_id.get(node.child1_id), by_id)
            or Bracket._has_placement(by_id.get(node.child2_id), by_id)
        )


class Match(TimeStampedModel):
    class Status(models.TextChoices):
        UPCOMING = "UPCOMING", "À venir"
        STARTED = "STARTED", "En cours"
        FINISHED = "FINISHED", "Terminé"

    bracket = models.ForeignKey(
        Bracket,
        on_delete=models.CASCADE,
        related_name="matches",
    )
    pair1 = models.ForeignKey(
        "players.Pair",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="matches_as_pair1",
    )
    pair2 = models.ForeignKey(
        "players.Pair",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="matches_as_pair2",
    )
    round = models.CharField(max_length=30, choices=Round.choices)
    match_number = models.PositiveSmallIntegerField()
    order = models.PositiveIntegerField(default=0)
    game_format = models.CharField(
        max_length=2,
        choices=Tournament.GameFormat.choices,
        blank=True,
        default="",
    )
    score = models.CharField(max_length=50, blank=True, default="")
    child1 = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="parent_as_child1",
    )
    child2 = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="parent_as_child2",
    )
    winner = models.ForeignKey(
        "players.Pair",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="won_matches",
    )
    disabled = models.BooleanField(default=False)
    pair1_can_be_placed = models.BooleanField(default=True)
    pair2_can_be_placed = models.BooleanField(default=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.UPCOMING,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["round", "match_number"]

    def __str__(self) -> str:
        return f"{self.get_round_display()} #{self.match_number}"

    def get_display_round(self) -> str:
        """Return the user-facing round label.

        For classification brackets (`bracket.start_place is not None`),
        the label reflects the range of places still at stake at this
        round, e.g. "Places 13-16" then "Places 13-14", rather than the
        generic Round label ("Demies", "Finale"...). The main bracket is
        unaffected and keeps the standard `get_round_display()` label.
        """
        start_place = self.bracket.start_place
        if start_place is None:
            return self.get_round_display()

        return _place_range_label(start_place, self.bracket.dimension, self.round)
