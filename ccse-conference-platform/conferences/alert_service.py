"""Live in-app reminders derived from saved records; no invented deadlines."""
import hashlib
import json
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from .permissions import can_review


class AlertReadState(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    key = models.CharField(max_length=64)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'key'], name='unique_user_alert_read')]


def alert_feed(user):
    from .models import Deadline, ExtractionCandidate
    from .planning_models import OutcomeReport
    today = timezone.localdate()
    horizon = today + timezone.timedelta(days=30)
    items = []

    def add(kind, identity, revision, title, message, href, due=None, **extra):
        days = (due - today).days if due else None
        urgency = 'overdue' if days is not None and days < 0 else 'today' if days == 0 else 'soon' if days is not None and days <= 7 else 'upcoming' if due else 'review'
        key = hashlib.sha256(json.dumps([kind, identity, revision], sort_keys=True, default=str).encode()).hexdigest()
        items.append(dict(key=key, kind=kind, title=title, message=message, href=href,
            due_date=due, days=days, urgency=urgency, **extra))

    # Past events stay in history. Unknown event dates never imply a precise event time.
    active_edition = (Q(edition__end_date__gte=today) |
        Q(edition__end_date__isnull=True, edition__start_date__gte=today) |
        Q(edition__end_date__isnull=True, edition__start_date__isnull=True, edition__year__gte=today.year))
    deadlines = Deadline.objects.filter(is_active=True, date__lte=horizon).filter(active_edition).select_related('edition__conference')
    for deadline in deadlines:
        add('deadline', deadline.pk, [deadline.date, deadline.time, deadline.timezone, deadline.type, deadline.source_url],
            f'{deadline.type.replace("_", " ")} · {deadline.edition}',
            'Check the published source before acting on this deadline.',
            f'/conference/{deadline.edition.conference_id}', deadline.date,
            timezone=deadline.timezone or '', source_url=deadline.source_url or '')

    for report in OutcomeReport.objects.filter(follow_up_completed=False, follow_up_date__lte=horizon).select_related('edition__conference'):
        add('follow_up', report.pk, [report.follow_up_date, report.follow_up],
            f'Follow-up · {report.edition}', report.follow_up or 'Review the open follow-up action.',
            f'/plans/{report.edition_id}', report.follow_up_date, timezone='', source_url='')

    if can_review(user):
        pending = ExtractionCandidate.objects.filter(status='needs_review')
        count = pending.count()
        if count:
            ids = list(pending.order_by('pk').values_list('pk', flat=True))
            add('review', 'pending', ids, f'{count} AI suggestion{"s" if count != 1 else ""} awaiting review',
                'Inspect the source evidence, then approve, correct, or reject the proposed information.',
                '/research', timezone='', source_url='')

    read = set(AlertReadState.objects.filter(user=user, key__in=[x['key'] for x in items]).values_list('key', flat=True))
    for item in items:
        item['read'] = item['key'] in read
    priority = {'overdue': 0, 'today': 1, 'soon': 2, 'review': 3, 'upcoming': 4}
    items.sort(key=lambda x: (priority[x['urgency']], x['due_date'] or horizon, x['key']))
    return {'today': today, 'window_days': 30, 'results': items, 'total': len(items),
        'unread_count': sum(not x['read'] for x in items),
        'urgent_count': sum(x['urgency'] in ['overdue', 'today', 'soon'] for x in items),
        'overdue_count': sum(x['urgency'] == 'overdue' for x in items)}
