from django.contrib import admin
from django.urls import include, path
from conferences import ai_views, platform_api

urlpatterns = [
    path("app/", platform_api.application, name="workspace"),
    path("health/", platform_api.health),
    path("api/platform/", include("conferences.platform_urls")),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("api/ai/session/", ai_views.session_info, name="ai-session"),
    path("api/ai/extract/", ai_views.extract, name="ai-extract"),
    path("api/ai/candidates/", ai_views.candidate_list, name="ai-candidates"),
    path("api/ai/candidates/<int:candidate_id>/", ai_views.candidate_detail, name="ai-candidate"),
    path("", include("conferences.urls")),
]
