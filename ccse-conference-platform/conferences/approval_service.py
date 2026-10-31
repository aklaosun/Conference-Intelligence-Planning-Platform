"""Transactional review-to-catalog approval, preserving original AI payloads and past editions."""
import copy
from django.db import transaction
from django.utils import timezone as django_timezone
from .models import (
    Conference, ConferenceEdition, Deadline, RegistrationPrice, ExtractionCandidate,
    InformationStatus, VerificationStatus,
)
from .review_validation import (
    ReviewStateError, ReviewValidationError, validate_fields, plain_values,
    reviewed_rows, source_map, source_url, json_ready,
)

KEY_EDITION_FIELDS = ["start_date","end_date","location"]
CONFERENCE_FIELDS = ["organizer","themes","target_audience"]
EDITION_FIELDS = ["start_date","end_date","start_time","timezone","location","attendance_format"]

def approve_candidate(candidate, edited_fields=None, reviewer="", *, decision=None):
    with transaction.atomic():
        locked = ExtractionCandidate.objects.select_for_update().get(pk=candidate.pk)
        if locked.status != ExtractionCandidate.Status.NEEDS_REVIEW:
            raise ReviewStateError("This candidate has already been reviewed.")
        payload = locked.raw_payload
        edits = edited_fields or {}
        if payload.get("conflicts") and decision is None:
            raise ReviewValidationError("Resolve the conflicts in the integrated review workbench before approving.")
        if decision is None:
            effective = plain_values(payload)
            effective.update(edits)
            values = validate_fields(locked,effective)
            deadlines = reviewed_rows(payload.get("deadlines",[]),"deadlines",payload,locked.requested_url,legacy=True)
            prices = reviewed_rows(payload.get("registration_prices",[]),"registration_prices",payload,locked.requested_url,legacy=True)
            notes, decisions, replace_rows = "", [], False
            explicit = set(edits)
        else:
            values = decision["fields"]
            deadlines, prices = decision["deadlines"], decision["registration_prices"]
            notes, decisions = decision["notes"], decision["conflict_decisions"]
            replace_rows = decision["replace_existing_rows"]
            originals = plain_values(payload)
            explicit = {name for name,value in values.items() if json_ready(value)!=originals.get(name)}
        # Case-insensitive matching avoids duplicating a conference over capitalization corrections.
        conference = Conference.objects.filter(name__iexact=values["conference_name"]).first()
        if conference is None:
            # Spreadsheet labels can differ from official titles. Match an exact
            # canonical website identity; ambiguity requires manual cleanup.
            from .cac_import import website_identity
            identity = website_identity(locked.requested_url)
            matches = [c for c in Conference.objects.exclude(website="")
                       if identity and website_identity(c.website) == identity]
            if len(matches) > 1:
                raise ReviewValidationError("Multiple catalog conferences use this website. Resolve the duplicates before approval.")
            conference = matches[0] if matches else None
        if conference is None:
            conference = Conference.objects.create(name=values["conference_name"])
        conference = Conference.objects.select_for_update().get(pk=conference.pk)
        sources = source_map(payload)
        def metadata(name):
            original = (payload.get("fields",{}).get(name) or {})
            if not isinstance(original,dict):
                original = {}
            src = sources.get(str(original.get("source_id")),{})
            return {
                "source_id":original.get("source_id"),
                "source_url":original.get("source_url") or src.get("source_url") or src.get("url") or locked.requested_url,
                "evidence":original.get("evidence"), "reviewed_by":reviewer[:128],
                "reviewer_corrected":name in explicit,
            }
        for name in CONFERENCE_FIELDS:
            new = values.get(name)
            if name in explicit or new not in (None,"",[]):
                setattr(conference,name,new if name not in ("themes","target_audience") else new or [])
                conference.field_sources[name] = metadata(name)
        if not conference.website:
            conference.website = locked.requested_url
        conference.save()
        edition, created = ConferenceEdition.objects.get_or_create(conference=conference,year=values["year"])
        edition = ConferenceEdition.objects.select_for_update().get(pk=edition.pk)
        for name in EDITION_FIELDS:
            new = values.get(name)
            if name in explicit or new is not None:
                setattr(edition,name,new)
                edition.field_sources[name] = metadata(name)
        edition.source_url = locked.requested_url
        edition.information_status = (
            InformationStatus.COMPLETE if all(getattr(edition,n) not in (None,"") for n in KEY_EDITION_FIELDS)
            else InformationStatus.PARTIAL_INFORMATION)
        edition.verification_status = VerificationStatus.VERIFIED
        edition.last_verified_at = django_timezone.now()
        edition.save()
        if replace_rows:
            edition.deadlines.filter(is_active=True).update(is_active=False)
            edition.registration_prices.filter(is_active=True).update(is_active=False)
        # A changed date supersedes the prior active deadline for that track only.
        for row in deadlines:
            edition.deadlines.filter(type=row["type"],is_active=True).exclude(date=row["date"]).update(is_active=False)
            existing = edition.deadlines.filter(type=row["type"],date=row["date"]).order_by("pk").first()
            if existing is None:
                Deadline.objects.create(edition=edition,is_active=True,**row)
            else:
                for name,value in row.items():
                    setattr(existing,name,value)
                existing.is_active = True
                existing.save()
        for row in prices:
            existing = edition.registration_prices.filter(category=row["category"],rate_type=row["rate_type"],currency=row["currency"]).order_by("pk").first()
            if existing is None:
                RegistrationPrice.objects.create(edition=edition,is_active=True,**row)
            else:
                for name,value in row.items():
                    setattr(existing,name,value)
                existing.is_active = True
                existing.save()
        approved = copy.deepcopy(payload)
        approved["fields"] = {name:{**(payload.get("fields",{}).get(name) or {}),"value":json_ready(value),
                                   "reviewer_corrected":name in explicit} for name,value in values.items()}
        approved["deadlines"] = json_ready(deadlines)
        approved["registration_prices"] = json_ready(prices)
        approved["review"] = {"reviewer":reviewer[:128],"notes":notes,"conflict_decisions":decisions,
                              "replace_existing_rows":replace_rows}
        locked.status = ExtractionCandidate.Status.APPROVED
        locked.conference = conference
        locked.conference_edition = edition
        locked.reviewed_at = django_timezone.now()
        locked.reviewed_by = reviewer[:128]
        locked.reviewed_payload = approved
        locked.review_notes = notes
        locked.save()
        # Keep the caller's object in sync without mutating original extraction data.
        candidate.refresh_from_db()
        return edition

def reject_candidate(candidate, reviewer="", *, notes=""):
    with transaction.atomic():
        locked = ExtractionCandidate.objects.select_for_update().get(pk=candidate.pk)
        if locked.status != ExtractionCandidate.Status.NEEDS_REVIEW:
            raise ReviewStateError("This candidate has already been reviewed.")
        locked.status = ExtractionCandidate.Status.REJECTED
        locked.reviewed_at = django_timezone.now()
        locked.reviewed_by = reviewer[:128]
        locked.review_notes = notes
        locked.save()
        candidate.refresh_from_db()

