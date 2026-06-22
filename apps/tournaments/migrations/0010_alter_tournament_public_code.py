from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tournaments", "0009_backfill_tournament_public_code"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tournament",
            name="public_code",
            field=models.CharField(editable=False, max_length=8, unique=True),
        ),
    ]
