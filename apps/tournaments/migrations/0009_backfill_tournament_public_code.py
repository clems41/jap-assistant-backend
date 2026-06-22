import secrets

from django.db import migrations

# Re-declared locally from apps.common.utils, same spirit as
# apps/matches/migrations/0008_backfill_finished_status.py and
# 0010_backfill_match_order.py: migrations must not depend on application
# code, so this stays correct even if apps.common.utils changes later.
PUBLIC_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
PUBLIC_CODE_LENGTH = 8


def _generate_public_code() -> str:
    return "".join(
        secrets.choice(PUBLIC_CODE_ALPHABET) for _ in range(PUBLIC_CODE_LENGTH)
    )


def backfill_tournament_public_code(apps, schema_editor):
    Tournament = apps.get_model("tournaments", "Tournament")

    existing_codes = set(
        Tournament.objects.exclude(public_code="").values_list("public_code", flat=True)
    )

    tournaments_to_update = []
    for tournament in Tournament.objects.filter(public_code=""):
        code = _generate_public_code()
        while code in existing_codes:
            code = _generate_public_code()
        existing_codes.add(code)
        tournament.public_code = code
        tournaments_to_update.append(tournament)

    Tournament.objects.bulk_update(tournaments_to_update, ["public_code"])


class Migration(migrations.Migration):
    dependencies = [
        ("tournaments", "0008_tournament_public_code"),
    ]

    operations = [
        migrations.RunPython(
            backfill_tournament_public_code, migrations.RunPython.noop
        ),
    ]
