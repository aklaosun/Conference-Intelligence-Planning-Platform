"""Administrator connection checks and a narrowly scoped scheduled-report hook."""
import hmac
import os
from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from .ai_service import GeminiProvider, ExtractionError
from .platform_api import api, body, error, event
from .permissions import can_manage_workspace
from .report_delivery import send_due_reports


@api
@require_http_methods(['GET', 'POST'])
def connections(request):
    if not can_manage_workspace(request.user):
        return error('Administrator access is required.', 403)
    email_enabled = getattr(settings, 'WORKSPACE_EMAIL_ENABLED', False)
    result = {'gemini_configured': bool(os.environ.get('GEMINI_API_KEY', '').strip()),
              'gemini_model': os.environ.get('GEMINI_MODEL', 'gemini-3.5-flash-lite'),
              'email_enabled': email_enabled, 'sender': settings.DEFAULT_FROM_EMAIL if email_enabled else '',
              'test_recipient': request.user.email,
              'scheduler_configured': len(getattr(settings, 'REPORT_JOB_TOKEN', '')) >= 48}
    if request.method == 'POST':
        action = body(request).get('action')
        if action == 'check_gemini':
            try:
                model = GeminiProvider().check_access()
            except ExtractionError as exc:
                return error(str(exc), 502)
            result['message'] = f'Gemini connected. Model available: {model}. No content was generated.'
        elif action == 'test_email':
            if not email_enabled:
                return error('Configure the email provider and enable email delivery on the server first.')
            try:
                validate_email(request.user.email)
            except ValidationError:
                return error('Add a valid email address to your own account before sending a test.')
            try:
                accepted = send_mail('CCSE workspace email test',
                    'Your CCSE Conference Workspace email connection is working. '
                    'This is a test requested by your administrator account.\n\n'
                    + request.build_absolute_uri('/app/'),
                    settings.DEFAULT_FROM_EMAIL, [request.user.email], fail_silently=False)
                if accepted != 1:
                    raise ValueError
            except Exception:
                return error('Email was not confirmed as accepted. Check the sender verification, API key, quota, and Brevo activity log before retrying.', 502)
            event(request.user, 'email_test_requested', 'Email provider accepted an administrator test email.')
            result['message'] = 'The email provider accepted the test. Check your inbox and spam folder to confirm receipt.'
        else:
            return error('Unknown connection action.')
    return JsonResponse(result)


@csrf_exempt
@require_POST
def scheduled_reports(request):
    expected = getattr(settings, 'REPORT_JOB_TOKEN', '')
    supplied = request.headers.get('Authorization', '')
    if len(expected) < 48 or not hmac.compare_digest(supplied.encode(), ('Bearer ' + expected).encode()):
        return error('Not authorized.', 401)
    if not getattr(settings, 'WORKSPACE_EMAIL_ENABLED', False):
        return error('Email delivery is disabled.', 503)
    try:
        count = send_due_reports()
    except Exception:
        # Never return provider responses, addresses, tokens, or report data.
        return error('Report delivery was not confirmed. Inspect the email provider activity log before retrying.', 502)
    return JsonResponse({'accepted': count})
