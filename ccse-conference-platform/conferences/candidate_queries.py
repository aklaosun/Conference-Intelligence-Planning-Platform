from .models import ExtractionCandidate


def get_pending_candidates():
    return ExtractionCandidate.objects.filter(
        status=ExtractionCandidate.Status.NEEDS_REVIEW
    ).order_by("-submitted_at")


def get_candidate(candidate_id):
    return ExtractionCandidate.objects.filter(id=candidate_id).first()


def get_candidate_for_review(candidate_id):
    candidate = get_candidate(candidate_id)
    if candidate is None:
        return None

    payload = candidate.raw_payload
    return {
        "id": candidate.id,
        "status": candidate.status,
        "requested_url": candidate.requested_url,
        "submitted_at": candidate.submitted_at,
        "fields": payload.get("fields", {}),
        "sources": payload.get("sources", []),
        "deadlines": payload.get("deadlines", []),
        "registration_prices": payload.get("registration_prices", []),
        "warnings": payload.get("warnings", []),
    }