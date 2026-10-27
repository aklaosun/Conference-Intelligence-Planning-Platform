from django.contrib import admin

from .models import Conference, ConferenceEdition, Deadline, ExtractionCandidate, RegistrationPrice


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
    list_display = ("name", "organizer", "cac_relevant", "cdsa_relevant")
    list_filter = ("cac_relevant", "cdsa_relevant")
    search_fields = ("name", "organizer")
    inlines = [EditionInline]


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
