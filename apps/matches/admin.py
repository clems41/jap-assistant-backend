from django.contrib import admin

from .models import Bracket, Match


@admin.register(Bracket)
class BracketAdmin(admin.ModelAdmin):
    list_display = ["tournament", "dimension", "nb_top_seeds", "created_at"]
    list_filter = ["dimension"]
    raw_id_fields = ["tournament"]


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ["bracket", "round", "match_number", "pair1", "pair2", "game_format"]
    list_filter = ["round", "game_format"]
    raw_id_fields = ["bracket", "pair1", "pair2", "child1", "child2"]
