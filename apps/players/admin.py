from django.contrib import admin

from .models import Pair, Player


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ["last_name", "first_name", "license_number", "ranking"]
    search_fields = ["last_name", "first_name", "license_number"]


@admin.register(Pair)
class PairAdmin(admin.ModelAdmin):
    list_display = ["player1", "player2", "tournament", "weight"]
    list_filter = ["tournament"]
