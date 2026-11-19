from django.contrib import admin

from .models import Center, Conference, ConferenceEdition, Deadline, ExtractionCandidate, RegistrationPrice, Theme


class DeadlineInline(admin.TabularInline):
    model = Deadline
    extra = 0


class PriceInline(admin.TabularInline):
    model = RegistrationPrice
    extra = 0


class EditionInline(admin.TabularInline):
    model = ConferenceEdition
    extra = 0
    fields = ("year", "start_date", "end_date", "location", "information_status", "verification_status")
    show_change_link = True


@admin.register(Conference)
class ConferenceAdmin(admin.ModelAdmin):
    list_display = ("name", "organizer", "center_list")
    list_filter = ("centers", "themes")
    search_fields = ("name", "organizer", "themes__name")
    filter_horizontal = ("centers", "themes")
    inlines = [EditionInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("centers")

    @admin.display(description="Centers")
    def center_list(self, obj):
        return ", ".join(obj.center_codes)


@admin.register(Center)
class CenterAdmin(admin.ModelAdmin):
    list_display = ("code", "name")


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(ConferenceEdition)
class ConferenceEditionAdmin(admin.ModelAdmin):
    list_display = ("conference", "year", "start_date", "location", "information_status", "verification_status")
    list_filter = ("year", "information_status", "verification_status", "attendance_format")
    search_fields = ("conference__name", "location")
    inlines = [DeadlineInline, PriceInline]


@admin.register(ExtractionCandidate)
class ExtractionCandidateAdmin(admin.ModelAdmin):
    list_display = ("__str__", "status", "submitted_at", "reviewed_by")
    list_filter = ("status",)
    readonly_fields = ("submitted_at",)


admin.site.register(Deadline)
admin.site.register(RegistrationPrice)

from .planning_models import PlanningStage,ConferencePlan,BudgetLine,OutcomeReport,SelectionCriterion,CriterionRating,ActivityEvent,ReportSubscription,ReportDelivery
for model in [PlanningStage,ConferencePlan,BudgetLine,OutcomeReport,SelectionCriterion,CriterionRating,ReportSubscription]:
    admin.site.register(model)

class WorkspaceAuditAdmin(admin.ModelAdmin):
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
admin.site.register(ActivityEvent,WorkspaceAuditAdmin)
admin.site.register(ReportDelivery,WorkspaceAuditAdmin)
