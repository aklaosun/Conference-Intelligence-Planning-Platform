"""Read-only entry point for Jonathan's candidate review frontend."""
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render
from django.views.decorators.http import require_GET


@login_required
@permission_required("conferences.view_extractioncandidate", raise_exception=True)
@require_GET
def review_screen(request):
    return render(request, "conferences/review.html")
