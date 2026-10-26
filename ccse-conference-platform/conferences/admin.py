from django.contrib import admin
from .models import ExtractionCandidate

@admin.register(ExtractionCandidate)
class ExtractionCandidateAdmin(admin.ModelAdmin):
    list_display = ("id", "requested_url", "status", "submitted_at")
    list_filter = ("status",)
    readonly_fields = tuple(field.name for field in ExtractionCandidate._meta.fields)
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
