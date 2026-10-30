"""Django session/permission/CSRF protected integration endpoints."""
import json
import requests
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.urls import reverse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST, require_GET
from .ai_service import extract_and_stage, ExtractionError, CandidateValidationError
from .models import ExtractionCandidate

@login_required
@permission_required("conferences.add_extractioncandidate", raise_exception=True)
@require_POST
def extract(request):
    try:
        body = json.loads(request.body)
        if not isinstance(body, dict) or not isinstance(body.get("url"), str) or not body["url"].strip():
            raise ValueError()
        year = body.get("year")
        if year is not None and (type(year) is not int or not 1900 <= year <= 2200):
            raise ValueError()
        follow = body.get("follow_links", True)
        force = body.get("force", False)
        max_pages = body.get("max_pages", 3)
        sources = body.get("source_urls", [])
        if type(follow) is not bool or type(force) is not bool or type(max_pages) is not int or not 1 <= max_pages <= 5:
            raise ValueError()
        if not isinstance(sources, list) or len(sources) > 4 or any(not isinstance(u, str) or not u.strip() for u in sources):
            raise ValueError()
    except (ValueError, TypeError):
        return JsonResponse({"error": "Supply url, optional integer year, boolean follow_links/force, max_pages 1–5, and up to four source_urls."}, status=400)
    try:
        candidate = extract_and_stage(body["url"], year, follow_links=follow,
            source_urls=sources, max_pages=max_pages, force=force, monitor=True)
    except CandidateValidationError as exc:
        return JsonResponse({"error": str(exc)}, status=422)
    except ExtractionError as exc:
        return JsonResponse({"error": str(exc)}, status=503)
    except (ValueError, requests.RequestException):
        return JsonResponse({"error": "Website retrieval or extraction validation failed. No candidate saved."}, status=422)
    created = getattr(candidate, "_ai_created", True)
    return JsonResponse({"id": candidate.pk, "status": candidate.status,
                         "created": created, "payload": candidate.raw_payload, "reviewed_payload":candidate.reviewed_payload,
                         "conference_url":reverse("conferences:conference_detail",args=[candidate.conference_id]) if candidate.conference_id else None}, status=201 if created else 200)

@login_required
@permission_required("conferences.view_extractioncandidate", raise_exception=True)
@require_GET
def candidate_detail(request, candidate_id):
    candidate = get_object_or_404(ExtractionCandidate, pk=candidate_id)
    return JsonResponse({"id": candidate.pk, "status": candidate.status, "payload": candidate.raw_payload, "reviewed_payload":candidate.reviewed_payload, "conference_url":reverse("conferences:conference_detail",args=[candidate.conference_id]) if candidate.conference_id else None})

@login_required
@permission_required("conferences.view_extractioncandidate", raise_exception=True)
@require_GET
def candidate_list(request):
    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError()
    except ValueError:
        return JsonResponse({"error":"page must be positive and page_size must be 1–100."}, status=400)
    query = ExtractionCandidate.objects.order_by("-submitted_at", "-pk")
    status = request.GET.get("status", "needs_review")
    if status != "all":
        if status not in ExtractionCandidate.Status.values:
            return JsonResponse({"error":"Unknown candidate status."},status=400)
        query = query.filter(status=status)
    if request.GET.get("url"):
        query = query.filter(requested_url=request.GET["url"])
    total = query.count()
    rows = query[(page-1)*page_size:page*page_size]
    return JsonResponse({"count":total,"page":page,"page_size":page_size,
        "results":[{"id":c.pk,"status":c.status,"requested_url":c.requested_url,
            "submitted_at":c.submitted_at.isoformat(),
            "summary":c.raw_payload.get("summary", {"conference_name": c.raw_payload.get("fields",{}).get("conference_name",{}).get("value")}),
            "warning_count":len(c.raw_payload.get("warnings",[]))} for c in rows]})


@login_required
@ensure_csrf_cookie
@require_GET
def session_info(request):
    return JsonResponse({"csrf_token":get_token(request), "permissions":{
        "extract":request.user.has_perm("conferences.add_extractioncandidate"),
        "view_candidates":request.user.has_perm("conferences.view_extractioncandidate")}})
