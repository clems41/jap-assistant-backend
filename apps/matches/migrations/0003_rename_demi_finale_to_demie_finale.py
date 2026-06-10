from django.db import migrations, models


def rename_demi_finale(apps, schema_editor):
    Match = apps.get_model("matches", "Match")
    Match.objects.filter(round="DEMI_FINALE").update(round="DEMIE_FINALE")


class Migration(migrations.Migration):

    dependencies = [
        ("matches", "0002_add_winner_to_match"),
    ]

    operations = [
        migrations.RunPython(rename_demi_finale, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="match",
            name="round",
            field=models.CharField(
                max_length=30,
                choices=[
                    ("FINALE", "Finale"),
                    ("DEMIE_FINALE", "Demies"),
                    ("QUART_DE_FINALE", "Quarts"),
                    ("HUITIEME_DE_FINALE", "Huitièmes"),
                    ("SEIZIEME_DE_FINALE", "Seizièmes"),
                    ("TRENTE_DEUXIEME_DE_FINALE", "32èmes"),
                ],
            ),
        ),
    ]
