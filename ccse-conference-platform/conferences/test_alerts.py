import json
from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch
from django.contrib.auth.models import User, Group
from django.core.management import call_command
from django.test import TestCase, Client
from .models import Conference, ConferenceEdition, Deadline, ExtractionCandidate, AlertReadState
from .planning_models import OutcomeReport


class AlertTests(TestCase):
    def setUp(self):
        call_command('setup_platform', stdout=StringIO())
        self.user = User.objects.create_user('alert-viewer')
        self.user.groups.add(Group.objects.get(name='Viewers'))
        self.reviewer = User.objects.create_user('alert-reviewer')
        self.reviewer.groups.add(Group.objects.get(name='Coordinators'))
        self.client.force_login(self.user)
        self.today = date(2026, 11, 2)
        self.clock = patch('conferences.alert_service.timezone.localdate', return_value=self.today)
        self.clock.start(); self.addCleanup(self.clock.stop)
        self.conference = Conference.objects.create(name='Alert test conference')
        self.edition = ConferenceEdition.objects.create(conference=self.conference, year=2027, start_date=date(2027, 3, 1))

    def deadline(self, days=0, **kwargs):
        return Deadline.objects.create(edition=self.edition, type='early_registration', date=self.today+timedelta(days=days), **kwargs)

    def feed(self):
        response = self.client.get('/api/platform/alerts/')
        self.assertEqual(response.status_code, 200)
        return response.json()

    def mark(self, keys, action='read', client=None):
        return (client or self.client).post('/api/platform/alerts/', json.dumps({'keys': keys, 'action': action}), content_type='application/json')

    def test_requires_authentication(self):
        self.client.logout()
        self.assertEqual(self.client.get('/api/platform/alerts/').status_code, 401)

    def test_due_today_seven_day_and_thirty_day_boundaries(self):
        for days in [-1, 0, 7, 8, 30, 31]: self.deadline(days)
        feed = self.feed()
        self.assertEqual([x['days'] for x in feed['results']], [-1, 0, 7, 8, 30])
        self.assertEqual(feed['urgent_count'], 3)
        self.assertEqual(feed['overdue_count'], 1)

    def test_inactive_and_finished_event_deadlines_do_not_alert(self):
        self.deadline(0, is_active=False)
        self.edition.start_date = self.today-timedelta(days=20)
        self.edition.end_date = self.today-timedelta(days=18)
        self.edition.save(); self.deadline(-30)
        self.assertEqual(self.feed()['total'], 0)

    def test_current_multiday_event_still_alerts(self):
        self.edition.start_date = self.today-timedelta(days=1)
        self.edition.end_date = self.today+timedelta(days=1)
        self.edition.save(); self.deadline(0)
        self.assertEqual(self.feed()['total'], 1)

    def test_unknown_dates_do_not_resurrect_prior_year_deadlines(self):
        self.edition.start_date = None; self.edition.year = 2025; self.edition.save()
        self.deadline(-365)
        self.assertEqual(self.feed()['total'], 0)

    def test_source_timezone_is_retained_without_claiming_exact_cutoff(self):
        self.deadline(0, timezone='AoE', source_url='https://example.org/deadlines')
        item = self.feed()['results'][0]
        self.assertEqual(item['timezone'], 'AoE')
        self.assertEqual(item['urgency'], 'today')

    def test_read_state_is_personal_persistent_and_reversible(self):
        self.deadline(2)
        key = self.feed()['results'][0]['key']
        self.assertEqual(self.mark([key]).status_code, 200)
        self.client.logout(); self.client.force_login(self.user)
        self.assertEqual(self.feed()['unread_count'], 0)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.feed()['unread_count'], 1)
        self.client.force_login(self.user)
        self.assertEqual(self.mark([key], 'unread').status_code, 200)
        self.assertEqual(self.feed()['unread_count'], 1)

    def test_repeated_read_is_idempotent_and_does_not_change_deadline(self):
        deadline = self.deadline(2)
        key = self.feed()['results'][0]['key']
        self.mark([key]); self.mark([key])
        self.assertEqual(AlertReadState.objects.count(), 1)
        deadline.refresh_from_db(); self.assertTrue(deadline.is_active)

    def test_changed_deadline_returns_as_unread(self):
        deadline = self.deadline(2)
        old_key = self.feed()['results'][0]['key']; self.mark([old_key])
        deadline.date += timedelta(days=1); deadline.save()
        item = self.feed()['results'][0]
        self.assertNotEqual(item['key'], old_key); self.assertFalse(item['read'])
        self.assertEqual(self.mark([old_key]).status_code, 400)

    def test_follow_up_disappears_only_when_completed(self):
        report = OutcomeReport.objects.create(edition=self.edition, summary='Outcome', follow_up='Contact partner', follow_up_date=self.today)
        item = self.feed()['results'][0]
        self.assertEqual(item['kind'], 'follow_up'); self.assertEqual(item['href'], f'/plans/{self.edition.pk}')
        self.mark([item['key']]); self.assertEqual(self.feed()['total'], 1)
        report.follow_up_completed = True; report.save()
        self.assertEqual(self.feed()['total'], 0)

    def test_review_alert_is_role_scoped_and_resolves_after_review(self):
        candidate = ExtractionCandidate.objects.create(requested_url='https://example.org', raw_payload={})
        self.assertEqual(self.feed()['total'], 0)
        self.client.force_login(self.reviewer)
        item = self.feed()['results'][0]; self.assertEqual(item['kind'], 'review')
        candidate.status = 'approved'; candidate.save()
        self.assertEqual(self.feed()['total'], 0)

    def test_invalid_actions_and_forged_keys_are_rejected(self):
        for keys, action in [(['not-an-alert'], 'read'), ([1], 'read'), ([], 'delete')]:
            self.assertEqual(self.mark(keys, action).status_code, 400)
        self.assertEqual(AlertReadState.objects.count(), 0)

    def test_read_actions_require_csrf(self):
        client = Client(enforce_csrf_checks=True); client.force_login(self.user)
        self.assertEqual(self.mark([], client=client).status_code, 403)
