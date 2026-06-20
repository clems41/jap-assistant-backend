from django.db import migrations
from django.db.models import F


def backfill_finished_status(apps, schema_editor):
    Match = apps.get_model("matches", "Match")
    Match.objects.filter(winner__isnull=False).update(
        status="FINISHED", finished_at=F("updated_at")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("matches", "0007_match_finished_at_match_status"),
    ]

    operations = [
        migrations.RunPython(backfill_finished_status, migrations.RunPython.noop),
    ]
