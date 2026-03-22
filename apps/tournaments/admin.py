from django.contrib import admin

from apps.tournaments.models import TimeSlot, Tournament


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "league", "gender", "start_date", "location", "owner"]
    list_filter = ["category", "league", "gender", "owner"]
    search_fields = ["name", "location"]
    ordering = ["start_date", "name"]


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ["tournament", "start_time", "end_time", "courts_available"]
    list_filter = ["tournament"]
    ordering = ["tournament", "start_time"]
    raw_id_fields = ["tournament"]
