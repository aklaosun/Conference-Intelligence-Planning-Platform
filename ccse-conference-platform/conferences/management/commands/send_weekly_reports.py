"""Opt-in report delivery. Dry run by default; no email is sent without --send."""
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from conferences.planning_models import ReportSubscription,ReportDelivery
from conferences.reporting import planning_csv

class Command(BaseCommand):
    help='Preview due weekly CSV report emails; use --send only after SMTP and recipients are configured.'
    def add_arguments(self,parser):parser.add_argument('--send',action='store_true')
    def handle(self,*args,**options):
        today=timezone.localdate()
        period=today-timezone.timedelta(days=today.weekday())
        due=ReportSubscription.objects.filter(enabled=True,weekday=today.weekday())
        if options['send'] and not getattr(settings,'WORKSPACE_EMAIL_ENABLED',False):
            raise CommandError('WORKSPACE_EMAIL_ENABLED is false. No emails were sent.')
        sent=0
        for subscription in due:
            if not options['send']:
                self.stdout.write(f'Dry run: subscription {subscription.pk} is due for week {period}.')
                continue
            with transaction.atomic():
                delivery,_=ReportDelivery.objects.select_for_update().get_or_create(subscription=subscription,period=period)
                if delivery.sent_at:continue
                email=EmailMessage(f'CCSE conference planning report — week of {period}',
                    'Attached are the recorded plans, budgets, outcomes, and follow-ups. Blank amounts remain unknown; currencies are kept separate.',
                    settings.DEFAULT_FROM_EMAIL,[subscription.email])
                email.attach('conference-planning-outcomes.csv',planning_csv(),'text/csv')
                if email.send(fail_silently=False)!=1:raise CommandError('Email delivery did not succeed; the report was not marked sent.')
                delivery.sent_at=timezone.now();delivery.save(update_fields=['sent_at']);sent+=1
        self.stdout.write(f'{sent} email(s) sent.' if options['send'] else 'Dry run complete. No emails were sent.')
