from django.db import models


class InformationStatus(models.TextChoices):
    NOT_RESEARCHED = "NOT_RESEARCHED", "Not Researched"
    INFORMATION_NOT_PUBLISHED = "INFORMATION_NOT_PUBLISHED", "Information Not Yet Published"
    PARTIAL_INFORMATION = "PARTIAL_INFORMATION", "Partial Information"
    COMPLETE = "COMPLETE", "Complete"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION", "Needs Verification"


class VerificationStatus(models.TextChoices):
    NEEDS_REVIEW = "NEEDS_REVIEW", "Needs Review"
    VERIFIED = "VERIFIED", "Verified"
    REJECTED = "REJECTED", "Rejected"


class AttendanceFormat(models.TextChoices):
    IN_PERSON = "in_person", "In Person"
    VIRTUAL = "virtual", "Virtual"
    HYBRID = "hybrid", "Hybrid"


def theme_key(name):
    return " ".join(str(name).split()).casefold()


class CenterManager(models.Manager):
    def get_by_natural_key(self, code):
        return self.get(code=code)


class Center(models.Model):
    code = models.CharField(max_length=8, unique=True)
    name = models.CharField(max_length=120)

    objects = CenterManager()

    class Meta:
        ordering = ["code"]

    def natural_key(self):
        return (self.code,)

    def __str__(self):
        return self.code


class ThemeManager(models.Manager):
    def get_by_natural_key(self, key):
        return self.get(key=key)

    def for_names(self, names):
        themes = {}
        for name in names or []:
            label = " ".join(str(name).split())
            if not label or theme_key(label) in themes:
                continue
            theme, _ = self.get_or_create(key=theme_key(label), defaults={"name": label[:120]})
            themes[theme.key] = theme
        return list(themes.values())


class Theme(models.Model):
    name = models.CharField(max_length=120)
    key = models.CharField(max_length=120, unique=True, editable=False)

    objects = ThemeManager()

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.name = " ".join(self.name.split())
        self.key = theme_key(self.name)
        super().save(*args, **kwargs)

    def natural_key(self):
        return (self.key,)

    def __str__(self):
        return self.name


class Conference(models.Model):
    name = models.CharField(max_length=255, unique=True)
    organizer = models.CharField(max_length=255, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    target_audience = models.JSONField(default=list, blank=True)
    centers = models.ManyToManyField(Center, blank=True, related_name="conferences")
    themes = models.ManyToManyField(Theme, blank=True, related_name="conferences")
    field_sources = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def center_codes(self):
        return [center.code for center in self.centers.all()]

    @property
    def theme_names(self):
        return [theme.name for theme in self.themes.all()]

    def has_center(self, code):
        return code in self.center_codes

    def add_centers(self, *codes):
        self.centers.add(*Center.objects.filter(code__in=codes))

    def set_centers(self, codes):
        self.centers.set(Center.objects.filter(code__in=codes))

    def set_themes(self, names):
        self.themes.set(Theme.objects.for_names(names))


class ConferenceEdition(models.Model):
    conference = models.ForeignKey(Conference, on_delete=models.CASCADE, related_name="editions")
    year = models.IntegerField()

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    timezone = models.CharField(max_length=64, null=True, blank=True)

    location = models.CharField(max_length=255, null=True, blank=True)
    attendance_format = models.CharField(
        max_length=16, choices=AttendanceFormat.choices, null=True, blank=True
    )

    information_status = models.CharField(
        max_length=32, choices=InformationStatus.choices,
        default=InformationStatus.NOT_RESEARCHED,
    )
    verification_status = models.CharField(
        max_length=32, choices=VerificationStatus.choices,
        default=VerificationStatus.NEEDS_REVIEW,
    )

    source_url = models.URLField(null=True, blank=True)
    field_sources = models.JSONField(default=dict, blank=True)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("conference", "year")
        ordering = ["-year"]

    def __str__(self):
        return f"{self.conference.name} ({self.year})"


class Deadline(models.Model):
    edition = models.ForeignKey(ConferenceEdition, on_delete=models.CASCADE, related_name="deadlines")
    type = models.CharField(max_length=64)
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    timezone = models.CharField(max_length=64, null=True, blank=True)
    source_url = models.URLField(null=True, blank=True)
    evidence = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.edition} - {self.type} ({self.date})"


class RegistrationPrice(models.Model):
    edition = models.ForeignKey(ConferenceEdition, on_delete=models.CASCADE, related_name="registration_prices")
    category = models.CharField(max_length=128)
    rate_type = models.CharField(max_length=64)
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=8, default="USD")
    source_url = models.URLField(null=True, blank=True)
    evidence = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.edition} - {self.category} ({self.rate_type})"


class ExtractionCandidate(models.Model):
    class Status(models.TextChoices):
        NEEDS_REVIEW = "needs_review", "Needs Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    schema_version = models.CharField(max_length=16, default="1.0")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEEDS_REVIEW)

    conference = models.ForeignKey(
        Conference, null=True, blank=True, on_delete=models.SET_NULL, related_name="candidates"
    )
    conference_edition = models.ForeignKey(
        ConferenceEdition, null=True, blank=True, on_delete=models.SET_NULL, related_name="candidates"
    )

    requested_url = models.URLField()
    raw_payload = models.JSONField()
    reviewed_payload = models.JSONField(null=True, blank=True)
    review_notes = models.TextField(blank=True, default="")

    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=128, null=True, blank=True)

    def __str__(self):
        name = self.raw_payload.get("fields", {}).get("conference_name", {}).get("value", "Unknown")
        return f"Candidate: {name} ({self.status})"

# Domain modules keep the core conference and extraction contracts stable.
from .planning_models import (PlanningStage,ConferencePlan,BudgetLine,OutcomeReport,SelectionCriterion,CriterionRating,ActivityEvent,ReportSubscription,ReportDelivery)
from .access_models import AccessInvitation,LoginThrottle,UserPreference
from .alert_service import AlertReadState
