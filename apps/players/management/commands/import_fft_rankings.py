"""Management command to import FFT rankings from PDF files."""
import os

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.players.models import FFTRanking, FFTRankingMeta
from apps.players.services.pdf_parser_service import parse_fft_pdf
from apps.tournaments.models import Tournament


class Command(BaseCommand):
    help = "Import FFT rankings from PDF files. Use --men and/or --women with file paths."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--men",
            type=str,
            help="Path to men's ranking PDF file",
        )
        parser.add_argument(
            "--women",
            type=str,
            help="Path to women's ranking PDF file",
        )

    def handle(self, *args, **options) -> None:
        men_path = options.get("men")
        women_path = options.get("women")

        if not men_path and not women_path:
            raise CommandError(
                "Au moins un argument --men ou --women doit être fourni."
            )

        if men_path:
            self._import(men_path, Tournament.Gender.MALE)
        if women_path:
            self._import(women_path, Tournament.Gender.FEMALE)

    def _import(self, path: str, gender: str) -> None:
        if not os.path.exists(path):
            raise SystemExit(f"Fichier introuvable : {path}")

        entries = parse_fft_pdf(path)
        filename = os.path.basename(path)

        # Replace existing records for this gender
        FFTRanking.objects.filter(gender=gender).delete()

        FFTRanking.objects.bulk_create(
            [
                FFTRanking(
                    last_name=e.last_name,
                    first_name=e.first_name,
                    league=e.league,
                    ranking=e.ranking,
                    points=e.points,
                    gender=gender,
                    source_filename=filename,
                )
                for e in entries
            ]
        )

        FFTRankingMeta.objects.update_or_create(
            gender=gender,
            defaults={
                "last_imported_at": timezone.now(),
                "source_filename": filename,
                "entry_count": len(entries),
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Importé {len(entries)} classements ({gender}) depuis {filename}"
            )
        )
