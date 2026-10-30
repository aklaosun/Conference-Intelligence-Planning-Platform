"""Integrated candidate review endpoint for Jonathan's workbench."""
import json
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from .models import ExtractionCandidate
from .permissions import reviewer_required
from .approval_service import approve_candidate, reject_candidate
from .review_validation import validate_packet, ReviewStateError, ReviewValidationError

@login_required
@permission_required("conferences.view_extractioncandidate", raise_exception=True)
@require_GET
def review_screen(request):
    return render(request,"conferences/review.html")

@require_POST
@reviewer_required
def candidate_decision(request, candidate_id):
    try:
        packet = json.loads(request.body)
    except (ValueError,UnicodeDecodeError):
        return JsonResponse({"error":"Supply a JSON review packet."},status=400)
    candidate = get_object_or_404(ExtractionCandidate,pk=candidate_id)
    if candidate.status != ExtractionCandidate.Status.NEEDS_REVIEW:
        return JsonResponse({"error":"This candidate has already been reviewed.","status":candidate.status},status=409)
    try:
        decision = validate_packet(candidate,packet)
        reviewer = (request.user.get_full_name() or request.user.get_username())[:128]
        if decision["action"]=="approve":
            edition = approve_candidate(candidate,reviewer=reviewer,decision=decision)
        else:
            reject_candidate(candidate,reviewer=reviewer,notes=decision["notes"])
            edition = None
    except ReviewStateError as exc:
        return JsonResponse({"error":str(exc)},status=409)
    except ReviewValidationError as exc:
        return JsonResponse({"error":str(exc)},status=422)
    candidate.refresh_from_db()
    return JsonResponse({
        "id":candidate.pk,"status":candidate.status,"payload":candidate.raw_payload,
        "reviewed_payload":candidate.reviewed_payload,"review_notes":candidate.review_notes,
        "conference_id":candidate.conference_id,"edition_id":candidate.conference_edition_id,
        "conference_url":reverse("conferences:conference_detail",args=[candidate.conference_id]) if edition else None,
    })

