from django.apps import AppConfig


class TournamentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tournaments"

    def ready(self) -> None:
        from apps.tournaments.signals import register_signals

        register_signals()
