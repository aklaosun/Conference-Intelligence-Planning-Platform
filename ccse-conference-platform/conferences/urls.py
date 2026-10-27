from django.urls import path

from . import views

app_name = "conferences"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("conferences/", views.conference_list, name="conference_list"),
    path("conferences/export.csv", views.export_conferences_csv, name="export_csv"),
    path("conferences/new/", views.conference_create, name="conference_create"),
    path("conferences/<int:pk>/", views.conference_detail, name="conference_detail"),
    path("conferences/<int:pk>/edit/", views.conference_edit, name="conference_edit"),
    path("conferences/<int:conference_pk>/editions/new/", views.edition_create, name="edition_create"),
    path("editions/<int:pk>/edit/", views.edition_edit, name="edition_edit"),
    path("review/", views.candidate_list, name="candidate_list"),
    path("review/<int:pk>/", views.candidate_detail, name="candidate_detail"),
    path("review/<int:pk>/approve/", views.candidate_approve, name="candidate_approve"),
    path("review/<int:pk>/reject/", views.candidate_reject, name="candidate_reject"),
    path("api/candidates/", views.api_submit_candidate, name="api_submit_candidate"),
]
