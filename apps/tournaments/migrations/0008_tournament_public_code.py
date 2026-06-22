from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tournaments", "0007_add_pairs_count_to_tournament"),
    ]

    operations = [
        migrations.AddField(
            model_name="tournament",
            name="public_code",
            field=models.CharField(blank=True, default="", max_length=8),
        ),
    ]
