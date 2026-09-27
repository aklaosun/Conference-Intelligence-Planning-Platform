from django.db import models


# ---------------------------------------------------------------------------
# Status choices
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Trusted / verified tables — only written to on approval
# ---------------------------------------------------------------------------

class Conference(models.Model):
    """The conference itself (year-independent). E.g. 'Example Computing Conference'."""

    name = models.CharField(max_length=255, unique=True)
    organizer = models.CharField(max_length=255, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    themes = models.JSONField(default=list, blank=True)            # e.g. ["AI", "Cybersecurity"]
    target_audience = models.JSONField(default=list, blank=True)    # e.g. ["Researchers", "Students"]
    cac_relevant = models.BooleanField(default=False)
    cdsa_relevant = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ConferenceEdition(models.Model):
    """A specific yearly instance of a Conference. Never overwrites a prior year's edition."""

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
    last_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("conference", "year")
        ordering = ["-year"]

    def __str__(self):
        return f"{self.conference.name} ({self.year})"


class Deadline(models.Model):
    """A single deadline (registration, submission, etc.) tied to one Conference Edition."""

    edition = models.ForeignKey(ConferenceEdition, on_delete=models.CASCADE, related_name="deadlines")
    type = models.CharField(max_length=64)          # e.g. "early_registration", "abstract_submission"
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    timezone = models.CharField(max_length=64, null=True, blank=True)
    source_url = models.URLField(null=True, blank=True)
    evidence = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.edition} - {self.type} ({self.date})"


class RegistrationPrice(models.Model):
    """A registration price tier tied to one Conference Edition."""

    edition = models.ForeignKey(ConferenceEdition, on_delete=models.CASCADE, related_name="registration_prices")
    category = models.CharField(max_length=128)     # e.g. "General admission"
    rate_type = models.CharField(max_length=64)      # e.g. "early_registration"
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.CharField(max_length=8, default="USD")
    source_url = models.URLField(null=True, blank=True)
    evidence = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.edition} - {self.category} ({self.rate_type})"


# ---------------------------------------------------------------------------
# Staging table — raw AI output, untouched, awaiting human review
# ---------------------------------------------------------------------------

class ExtractionCandidate(models.Model):
    """
    One full extraction result from Gavin's AI component, stored exactly as
    received (raw_payload). Nothing here is trusted until a human approves it
    via the review screen -- approval copies selected data into the
    Conference / ConferenceEdition / Deadline / RegistrationPrice tables above.
    """

    class Status(models.TextChoices):
        NEEDS_REVIEW = "needs_review", "Needs Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    schema_version = models.CharField(max_length=16, default="1.0")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEEDS_REVIEW)

    # Set once a human approves and the candidate is linked to real records.
    conference = models.ForeignKey(
        Conference, null=True, blank=True, on_delete=models.SET_NULL, related_name="candidates"
    )
    conference_edition = models.ForeignKey(
        ConferenceEdition, null=True, blank=True, on_delete=models.SET_NULL, related_name="candidates"
    )

    requested_url = models.URLField()

    # Full original JSON from Gavin's extraction service (sources, fields,
    # registration_prices, deadlines, warnings -- everything, untouched).
    raw_payload = models.JSONField()

    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=128, null=True, blank=True)  # swap for FK to User later

    def __str__(self):
        name = self.raw_payload.get("fields", {}).get("conference_name", {}).get("value", "Unknown")
        return f"Candidate: {name} ({self.status})"
# Create your models here.
