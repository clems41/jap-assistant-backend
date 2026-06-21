from django.db import migrations

# Recopié en littéral depuis apps.matches.models.ROUNDS_BY_DIMENSION pour ne
# pas dépendre du code applicatif (même esprit que
# 0008_backfill_finished_status.py) : si ce dict évolue plus tard, cette
# migration de données doit continuer à produire le même résultat pour les
# tableaux déjà en base au moment où elle a été écrite.
ROUNDS_BY_DIMENSION: dict[int, list[str]] = {
    2: [
        "FINALE",
    ],
    4: [
        "DEMIE_FINALE",
        "FINALE",
    ],
    8: [
        "QUART_DE_FINALE",
        "DEMIE_FINALE",
        "FINALE",
    ],
    16: [
        "HUITIEME_DE_FINALE",
        "QUART_DE_FINALE",
        "DEMIE_FINALE",
        "FINALE",
    ],
    32: [
        "SEIZIEME_DE_FINALE",
        "HUITIEME_DE_FINALE",
        "QUART_DE_FINALE",
        "DEMIE_FINALE",
        "FINALE",
    ],
    64: [
        "TRENTE_DEUXIEME_DE_FINALE",
        "SEIZIEME_DE_FINALE",
        "HUITIEME_DE_FINALE",
        "QUART_DE_FINALE",
        "DEMIE_FINALE",
        "FINALE",
    ],
}


def _assign_order(bracket, start, matches_to_update):
    order = start
    rounds = ROUNDS_BY_DIMENSION[bracket.dimension]
    matches_by_round = {}
    for m in bracket.matches.all():
        matches_by_round.setdefault(m.round, []).append(m)
    children_by_source_round = {c.source_round: c for c in bracket.children.all()}

    for round_name in rounds:
        round_matches = sorted(
            matches_by_round.get(round_name, []), key=lambda m: m.match_number
        )
        for m in round_matches:
            m.order = order
            order += 1
        matches_to_update.extend(round_matches)

        child = children_by_source_round.get(round_name)
        if child is not None:
            order = _assign_order(child, order, matches_to_update)

    return order


def backfill_match_order(apps, schema_editor):
    Bracket = apps.get_model("matches", "Bracket")
    Match = apps.get_model("matches", "Match")

    for main_bracket in Bracket.objects.filter(parent__isnull=True):
        matches_to_update = []
        _assign_order(main_bracket, 1, matches_to_update)
        Match.objects.bulk_update(matches_to_update, ["order"])


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0009_match_order"),
    ]

    operations = [
        migrations.RunPython(backfill_match_order, migrations.RunPython.noop),
    ]
