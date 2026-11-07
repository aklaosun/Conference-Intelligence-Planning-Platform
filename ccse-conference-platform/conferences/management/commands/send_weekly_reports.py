"""Opt-in report delivery. Dry run by default; no email is sent without --send."""
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.utils import timezone
from conferences.planning_models import ReportSubscription
from conferences.report_delivery import send_due_reports

class Command(BaseCommand):
    help='Preview due weekly CSV report emails; use --send after the email provider and recipients are configured.'
    def add_arguments(self,parser):parser.add_argument('--send',action='store_true')
    def handle(self,*args,**options):
        today=timezone.localdate()
        period=today-timezone.timedelta(days=today.weekday())
        due=ReportSubscription.objects.filter(enabled=True,weekday=today.weekday())
        if options['send'] and not getattr(settings,'WORKSPACE_EMAIL_ENABLED',False):
            raise CommandError('WORKSPACE_EMAIL_ENABLED is false. No emails were sent.')
        if not options['send']:
            for subscription in due:
                self.stdout.write(f'Dry run: subscription {subscription.pk} is due for week {period}.')
            self.stdout.write('Dry run complete. No emails were sent.')
            return
        try:
            sent=send_due_reports()
        except Exception:
            raise CommandError('Email delivery was not confirmed. Check provider activity before retrying; unconfirmed reports were not marked sent.') from None
        self.stdout.write(f'{sent} email(s) accepted by the email provider.')
