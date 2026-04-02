from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_v1_patterns = [
    path("auth/", include("apps.users.urls")),
    path("tournaments/", include("apps.tournaments.urls")),
    path("tournaments/<int:tournament_id>/pairs/", include("apps.players.urls")),
    path("tournaments/<int:tournament_id>/bracket/", include("apps.brackets.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1_patterns)),
    # OpenAPI schema & Swagger UI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
