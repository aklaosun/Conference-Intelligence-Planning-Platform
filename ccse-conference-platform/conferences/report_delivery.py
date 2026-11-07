"""Due, explicitly subscribed reports; shared by the command and scheduler."""
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from .planning_models import ReportSubscription, ReportDelivery
from .reporting import planning_csv


def send_due_reports():
    if not getattr(settings, 'WORKSPACE_EMAIL_ENABLED', False):
        raise ValueError('Email delivery is disabled.')
    today = timezone.localdate()
    period = today - timezone.timedelta(days=today.weekday())
    sent = 0
    for subscription in ReportSubscription.objects.filter(enabled=True, weekday=today.weekday()):
        with transaction.atomic():
            delivery, _ = ReportDelivery.objects.select_for_update().get_or_create(subscription=subscription, period=period)
            if delivery.sent_at:
                continue
            email = EmailMessage(f'CCSE conference planning report — week of {period}',
                'Attached are the recorded plans, budgets, outcomes, and follow-ups. '
                'Blank amounts remain unknown; currencies are kept separate.',
                settings.DEFAULT_FROM_EMAIL, [subscription.email],
                headers={'IdempotencyKey': f'ccse-weekly-{subscription.pk}-{period}'})
            email.attach('conference-planning-outcomes.csv', planning_csv(), 'text/csv')
            if email.send(fail_silently=False) != 1:
                raise ValueError('Email was not accepted; the report was not marked sent.')
            delivery.sent_at = timezone.now()
            delivery.save(update_fields=['sent_at'])
            sent += 1
    return sent
