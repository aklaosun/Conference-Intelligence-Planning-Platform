import csv
import datetime
import hmac
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Min, Prefetch, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .approval_service import approve_candidate, reject_candidate
from .candidate_queries import get_pending_candidates
from .forms import (
    CandidateCorrectionForm,
    ConferenceForm,
    ConferenceSearchForm,
    DeadlineFormSet,
    EditionForm,
    PriceFormSet,
    RejectForm,
)
from .models import Conference, ConferenceEdition, Deadline, ExtractionCandidate, RegistrationPrice
from .permissions import editor_required, reviewer_required
from .review_validation import ReviewValidationError, ReviewStateError


@login_required
def dashboard(request):
    today = timezone.localdate()
    soon = today + datetime.timedelta(days=60)
    upcoming_deadlines = (
        Deadline.objects.filter(is_active=True, date__gte=today, date__lte=soon)
        .select_related("edition__conference")
        .order_by("date")[:10]
    )
    upcoming_editions = (
        ConferenceEdition.objects.filter(start_date__gte=today)
        .select_related("conference")
        .order_by("start_date")[:8]
    )
    context = {
        "conference_count": Conference.objects.count(),
        "edition_count": ConferenceEdition.objects.count(),
        "pending_count": ExtractionCandidate.objects.filter(
            status=ExtractionCandidate.Status.NEEDS_REVIEW
        ).count(),
        "needs_verification_count": ConferenceEdition.objects.exclude(
            verification_status="VERIFIED"
        ).count(),
        "upcoming_deadlines": upcoming_deadlines,
        "upcoming_editions": upcoming_editions,
    }
    return render(request, "conferences/dashboard.html", context)


def filtered_conferences(params):
    form = ConferenceSearchForm(params or None)
    conferences = Conference.objects.all()
    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            q = data["q"]
            conferences = conferences.filter(
                Q(name__icontains=q)
                | Q(organizer__icontains=q)
                | Q(editions__location__icontains=q)
                | Q(themes__icontains=q)
            )
        center = data["center"]
        if center == "cac":
            conferences = conferences.filter(cac_relevant=True)
        elif center == "cdsa":
            conferences = conferences.filter(cdsa_relevant=True)
        elif center == "both":
            conferences = conferences.filter(cac_relevant=True, cdsa_relevant=True)

        edition_filter = Q()
        if data["year"]:
            edition_filter &= Q(editions__year=data["year"])
        if data["information_status"]:
            edition_filter &= Q(editions__information_status=data["information_status"])
        if data["verification_status"]:
            edition_filter &= Q(editions__verification_status=data["verification_status"])
        if data["attendance_format"]:
            edition_filter &= Q(editions__attendance_format=data["attendance_format"])
        if data["upcoming_only"]:
            edition_filter &= Q(editions__start_date__gte=timezone.localdate())
        if edition_filter:
            conferences = conferences.filter(edition_filter)

    conferences = (
        conferences.distinct()
        .annotate(edition_total=Count("editions", distinct=True))
        .order_by("name")
    )
    return form, conferences


@login_required
def conference_list(request):
    form, conferences = filtered_conferences(request.GET)
    page = Paginator(conferences, 25).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "conferences/conference_list.html", {
        "form": form,
        "page": page,
        "query": query.urlencode(),
    })


@login_required
def conference_detail(request, pk):
    conference = get_object_or_404(Conference, pk=pk)
    editions = conference.editions.prefetch_related(
        Prefetch("deadlines", queryset=Deadline.objects.filter(is_active=True).order_by("date")),
        Prefetch("registration_prices", queryset=RegistrationPrice.objects.filter(is_active=True)),
    )
    return render(request, "conferences/conference_detail.html", {
        "conference": conference,
        "editions": editions,
    })


@editor_required
def conference_create(request):
    form = ConferenceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        conference = form.save()
        messages.success(request, f"Added {conference.name}.")
        return redirect("conferences:conference_detail", pk=conference.pk)
    return render(request, "conferences/conference_form.html", {"form": form})


@editor_required
def conference_edit(request, pk):
    conference = get_object_or_404(Conference, pk=pk)
    form = ConferenceForm(request.POST or None, instance=conference)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Conference saved.")
        return redirect("conferences:conference_detail", pk=conference.pk)
    return render(request, "conferences/conference_form.html", {"form": form, "conference": conference})


def _edition_form_page(request, conference, edition=None):
    data = request.POST or None
    form = EditionForm(data, instance=edition)
    deadline_formset = DeadlineFormSet(data, instance=edition, prefix="deadlines")
    price_formset = PriceFormSet(data, instance=edition, prefix="prices")

    if request.method == "POST":
        if edition is None:
            form.instance.conference = conference
        if form.is_valid() and deadline_formset.is_valid() and price_formset.is_valid():
            with transaction.atomic():
                saved = form.save()
                deadline_formset.instance = saved
                price_formset.instance = saved
                deadline_formset.save()
                price_formset.save()
            messages.success(request, f"Saved {saved}.")
            return redirect("conferences:conference_detail", pk=conference.pk)

    return render(request, "conferences/edition_form.html", {
        "conference": conference,
        "edition": edition,
        "form": form,
        "deadline_formset": deadline_formset,
        "price_formset": price_formset,
    })


@editor_required
def edition_create(request, conference_pk):
    conference = get_object_or_404(Conference, pk=conference_pk)
    return _edition_form_page(request, conference)


@editor_required
def edition_edit(request, pk):
    edition = get_object_or_404(ConferenceEdition.objects.select_related("conference"), pk=pk)
    return _edition_form_page(request, edition.conference, edition)


@login_required
def export_conferences_csv(request):
    _, conferences = filtered_conferences(request.GET)
    editions = (
        ConferenceEdition.objects.filter(conference__in=conferences)
        .select_related("conference")
        .annotate(next_deadline=Min("deadlines__date", filter=Q(deadlines__is_active=True)))
        .order_by("conference__name", "-year")
    )
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="conferences.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Conference", "Organizer", "Website", "CAC", "CDSA", "Themes", "Year", "Start date",
        "End date", "Location", "Format", "Information status", "Verification status",
        "Earliest deadline", "Source URL",
    ])
    for e in editions:
        c = e.conference
        writer.writerow([
            c.name, c.organizer or "", c.website or "", "Yes" if c.cac_relevant else "No",
            "Yes" if c.cdsa_relevant else "No", "; ".join(c.themes or []), e.year,
            e.start_date or "", e.end_date or "", e.location or "",
            e.get_attendance_format_display() if e.attendance_format else "",
            e.get_information_status_display(), e.get_verification_status_display(),
            e.next_deadline or "", e.source_url or "",
        ])
    return response


@login_required
def candidate_list(request):
    status = request.GET.get("status", ExtractionCandidate.Status.NEEDS_REVIEW)
    candidates = ExtractionCandidate.objects.order_by("-submitted_at")
    if status == ExtractionCandidate.Status.NEEDS_REVIEW:
        candidates = get_pending_candidates()
    elif status in ExtractionCandidate.Status.values:
        candidates = candidates.filter(status=status)
    else:
        status = "all"
    page = Paginator(candidates, 25).get_page(request.GET.get("page"))
    return render(request, "conferences/candidate_list.html", {
        "page": page,
        "status": status,
        "statuses": ExtractionCandidate.Status.choices,
    })


def _field_rows(payload):
    rows = []
    sources = {str(s.get("id")):s for s in payload.get("sources",[]) if isinstance(s,dict)}
    for name, entry in (payload.get("fields") or {}).items():
        if isinstance(entry, dict):
            extra = {k: v for k, v in entry.items() if k not in ("value", "source_url", "evidence", "confidence")}
            rows.append({
                "name": name,
                "value": entry.get("value"),
                "source_url": entry.get("source_url") or sources.get(str(entry.get("source_id")),{}).get("source_url"),
                "evidence": entry.get("evidence"),
                "confidence": entry.get("confidence"),
                "extra": extra,
            })
        else:
            rows.append({"name": name, "value": entry})
    return rows


@login_required
def candidate_detail(request, pk):
    candidate = get_object_or_404(ExtractionCandidate, pk=pk)
    payload = candidate.raw_payload or {}
    is_open = candidate.status == ExtractionCandidate.Status.NEEDS_REVIEW
    form = CandidateCorrectionForm(candidate=candidate) if is_open else None
    existing = None
    name = CandidateCorrectionForm.values_from_payload(payload).get("conference_name")
    if name:
        existing = Conference.objects.filter(name__iexact=name).first()
    return render(request, "conferences/candidate_detail.html", {
        "candidate": candidate,
        "is_open": is_open,
        "field_rows": _field_rows(payload),
        "deadlines": payload.get("deadlines") or [],
        "prices": payload.get("registration_prices") or [],
        "warnings": payload.get("warnings") or [],
        "sources": payload.get("sources") or [],
        "form": form,
        "reject_form": RejectForm() if is_open else None,
        "existing": existing,
    })


def _reviewer_name(user):
    return user.get_full_name() or user.get_username()


@require_POST
@reviewer_required
def candidate_approve(request, pk):
    with transaction.atomic():
        candidate = get_object_or_404(ExtractionCandidate.objects.select_for_update(), pk=pk)
        if candidate.status != ExtractionCandidate.Status.NEEDS_REVIEW:
            messages.warning(request, "That suggestion was already reviewed.")
            return redirect("conferences:candidate_detail", pk=pk)

        form = CandidateCorrectionForm(request.POST, candidate=candidate)
        if not form.is_valid():
            payload = candidate.raw_payload or {}
            return render(request, "conferences/candidate_detail.html", {
                "candidate": candidate,
                "is_open": True,
                "field_rows": _field_rows(payload),
                "deadlines": payload.get("deadlines") or [],
                "prices": payload.get("registration_prices") or [],
                "warnings": payload.get("warnings") or [],
                "sources": payload.get("sources") or [],
                "form": form,
                "reject_form": RejectForm(),
            }, status=400)

        edits = form.edited_fields()
        try:
            edition = approve_candidate(candidate, edited_fields=edits, reviewer=_reviewer_name(request.user))
        except (ReviewValidationError, ReviewStateError) as exc:
            messages.error(request, str(exc))
            return redirect("conferences:candidate_detail", pk=pk)

    if edits:
        messages.success(request, f"Corrected {len(edits)} field(s) and approved {edition}.")
    else:
        messages.success(request, f"Approved {edition}.")
    return redirect("conferences:candidate_list")


@require_POST
@reviewer_required
def candidate_reject(request, pk):
    form = RejectForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Tick the box to confirm the rejection.")
        return redirect("conferences:candidate_detail", pk=pk)
    with transaction.atomic():
        candidate = get_object_or_404(ExtractionCandidate.objects.select_for_update(), pk=pk)
        if candidate.status != ExtractionCandidate.Status.NEEDS_REVIEW:
            messages.warning(request, "That suggestion was already reviewed.")
            return redirect("conferences:candidate_detail", pk=pk)
        reject_candidate(candidate, reviewer=_reviewer_name(request.user))
    messages.success(request, "Suggestion rejected.")
    return redirect("conferences:candidate_list")


def _token_ok(request):
    expected = getattr(settings, "EXTRACTION_API_TOKEN", "")
    if not expected:
        return False
    header = request.headers.get("Authorization", "")
    supplied = header[7:] if header.startswith("Bearer ") else ""
    return hmac.compare_digest(supplied.encode(), expected.encode())


@csrf_exempt
@require_POST
def api_submit_candidate(request):
    if not _token_ok(request):
        return JsonResponse({"error": "invalid or missing token"}, status=401)
    try:
        payload = json.loads(request.body or b"")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "body must be JSON"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "body must be a JSON object"}, status=400)

    errors = []
    requested_url = payload.get("requested_url") or payload.get("url")
    if not requested_url:
        errors.append("requested_url is required")
    values = CandidateCorrectionForm.values_from_payload(payload)
    if not values.get("conference_name"):
        errors.append("fields.conference_name.value is required")
    if not values.get("year"):
        errors.append("fields.year.value is required")
    for key in ("deadlines", "registration_prices", "warnings", "sources"):
        if key in payload and not isinstance(payload[key], list):
            errors.append(f"{key} must be a list")
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    candidate = ExtractionCandidate.objects.create(
        schema_version=str(payload.get("schema_version", "1.0"))[:16],
        requested_url=requested_url,
        raw_payload=payload,
    )
    return JsonResponse({"id": candidate.pk, "status": candidate.status}, status=201)
