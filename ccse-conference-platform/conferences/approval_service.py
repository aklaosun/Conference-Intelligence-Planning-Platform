"""
Approval logic for extraction candidates.

Called when a human clicks "Approve" on Jonathan's review screen. Converts
one ExtractionCandidate's raw_payload into trusted Conference / Conference
Edition / Deadline / RegistrationPrice records.
"""

from django.utils import timezone as django_timezone

from .models import (
    Conference,
    ConferenceEdition,
    Deadline,
    RegistrationPrice,
    ExtractionCandidate,
    InformationStatus,
    VerificationStatus,
)


def approve_candidate(candidate: ExtractionCandidate, edited_fields: dict | None = None,
                       reviewer: str = "") -> ConferenceEdition:
    payload = candidate.raw_payload
    fields = payload.get("fields", {})
    edited_fields = edited_fields or {}

    def value_of(field_name):
        if field_name in edited_fields:
            return edited_fields[field_name]
        return fields.get(field_name, {}).get("value")

    name = value_of("conference_name")
    conference, _ = Conference.objects.get_or_create(
        name=name,
        defaults={
            "organizer": value_of("organizer"),
            "themes": value_of("themes") or [],
            "target_audience": value_of("target_audience") or [],
        },
    )

    year = value_of("year")
    edition, created = ConferenceEdition.objects.get_or_create(
        conference=conference,
        year=year,
        defaults={
            "start_date": value_of("start_date"),
            "end_date": value_of("end_date"),
            "start_time": value_of("start_time"),
            "timezone": value_of("timezone"),
            "location": value_of("location"),
            "attendance_format": value_of("attendance_format"),
            "source_url": candidate.requested_url,
        },
    )

    if not created:
        field_map = {
            "start_date": value_of("start_date"),
            "end_date": value_of("end_date"),
            "start_time": value_of("start_time"),
            "timezone": value_of("timezone"),
            "location": value_of("location"),
            "attendance_format": value_of("attendance_format"),
        }
        for attr, new_value in field_map.items():
            if new_value is not None and getattr(edition, attr) in (None, ""):
                setattr(edition, attr, new_value)

    edition.information_status = InformationStatus.COMPLETE
    edition.verification_status = VerificationStatus.VERIFIED
    edition.last_verified_at = django_timezone.now()
    edition.save()

    for d in payload.get("deadlines", []):
        Deadline.objects.get_or_create(
            edition=edition,
            type=d.get("type"),
            date=d.get("date"),
            defaults={
                "time": d.get("time"),
                "timezone": d.get("timezone"),
                "evidence": d.get("evidence"),
            },
        )

    for p in payload.get("registration_prices", []):
        RegistrationPrice.objects.get_or_create(
            edition=edition,
            category=p.get("category"),
            rate_type=p.get("rate_type"),
            defaults={
                "amount": p.get("amount"),
                "currency": p.get("currency", "USD"),
                "evidence": p.get("evidence"),
            },
        )

    candidate.status = ExtractionCandidate.Status.APPROVED
    candidate.conference = conference
    candidate.conference_edition = edition
    candidate.reviewed_at = django_timezone.now()
    candidate.reviewed_by = reviewer
    candidate.save()

    return edition


def reject_candidate(candidate: ExtractionCandidate, reviewer: str = "") -> None:
    candidate.status = ExtractionCandidate.Status.REJECTED
    candidate.reviewed_at = django_timezone.now()
    candidate.reviewed_by = reviewer
    candidate.save()