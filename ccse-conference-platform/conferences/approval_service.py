from django.db import transaction
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

KEY_EDITION_FIELDS = ["start_date", "end_date", "location"]


def approve_candidate(candidate, edited_fields=None, reviewer=""):
    payload = candidate.raw_payload
    fields = payload.get("fields", {})
    edited_fields = edited_fields or {}

    def value_of(field_name):
        if field_name in edited_fields:
            return edited_fields[field_name]
        return fields.get(field_name, {}).get("value")

    def field_meta(field_name):
        f = fields.get(field_name, {})
        return {"source_id": f.get("source_id"), "evidence": f.get("evidence")}

    with transaction.atomic():
        name = value_of("conference_name")
        conference, created = Conference.objects.get_or_create(name=name)

        conference.organizer = value_of("organizer") or conference.organizer
        conference.themes = value_of("themes") or conference.themes
        conference.target_audience = value_of("target_audience") or conference.target_audience

        conference.field_sources.update({
            "organizer": field_meta("organizer"),
            "themes": field_meta("themes"),
            "target_audience": field_meta("target_audience"),
        })
        conference.save()

        year = value_of("year")
        edition, edition_created = ConferenceEdition.objects.get_or_create(
            conference=conference, year=year
        )

        edition.start_date = value_of("start_date") or edition.start_date
        edition.end_date = value_of("end_date") or edition.end_date
        edition.start_time = value_of("start_time") or edition.start_time
        edition.timezone = value_of("timezone") or edition.timezone
        edition.location = value_of("location") or edition.location
        edition.attendance_format = value_of("attendance_format") or edition.attendance_format
        edition.source_url = candidate.requested_url

        edition.field_sources.update({
            "start_date": field_meta("start_date"),
            "end_date": field_meta("end_date"),
            "location": field_meta("location"),
            "attendance_format": field_meta("attendance_format"),
        })

        missing_something = False
        for f in KEY_EDITION_FIELDS:
            if getattr(edition, f) in (None, ""):
                missing_something = True
                break

        if missing_something:
            edition.information_status = InformationStatus.PARTIAL_INFORMATION
        else:
            edition.information_status = InformationStatus.COMPLETE

        edition.verification_status = VerificationStatus.VERIFIED
        edition.last_verified_at = django_timezone.now()
        edition.save()

        edition.deadlines.filter(is_active=True).update(is_active=False)

        for d in payload.get("deadlines", []):
            Deadline.objects.update_or_create(
                edition=edition,
                type=d.get("type"),
                date=d.get("date"),
                defaults={
                    "time": d.get("time"),
                    "timezone": d.get("timezone"),
                    "evidence": d.get("evidence"),
                    "is_active": True,
                },
            )

        edition.registration_prices.filter(is_active=True).update(is_active=False)

        for p in payload.get("registration_prices", []):
            RegistrationPrice.objects.update_or_create(
                edition=edition,
                category=p.get("category"),
                rate_type=p.get("rate_type"),
                defaults={
                    "amount": p.get("amount"),
                    "currency": p.get("currency", "USD"),
                    "evidence": p.get("evidence"),
                    "is_active": True,
                },
            )

        candidate.status = ExtractionCandidate.Status.APPROVED
        candidate.conference = conference
        candidate.conference_edition = edition
        candidate.reviewed_at = django_timezone.now()
        candidate.reviewed_by = reviewer
        candidate.save()

    return edition


def reject_candidate(candidate, reviewer=""):
    candidate.status = ExtractionCandidate.Status.REJECTED
    candidate.reviewed_at = django_timezone.now()
    candidate.reviewed_by = reviewer
    candidate.save()