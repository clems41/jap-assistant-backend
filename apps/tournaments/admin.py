from django.contrib import admin

from apps.tournaments.models import Tournament


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "league", "gender", "start_date", "location", "owner"]
    list_filter = ["category", "league", "gender", "owner"]
    search_fields = ["name", "location"]
    ordering = ["start_date", "name"]
