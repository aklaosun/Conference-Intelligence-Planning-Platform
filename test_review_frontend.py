"""Frontend route plus existing AI contract integration checks; no provider calls."""
import json
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth.models import Permission, User
from django.contrib.staticfiles import finders
from django.test import Client, TestCase
from django.urls import reverse
from .models import ConferenceEdition, ExtractionCandidate


class ReviewFrontendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('review-user', password='test-only-password')
        self.user.user_permissions.add(*Permission.objects.filter(
            codename__in=['view_extractioncandidate', 'add_extractioncandidate']))
        self.payload = json.loads((Path(__file__).resolve().parents[2] / 'examples/synthetic-candidate.json').read_text())
        self.candidate = ExtractionCandidate.objects.create(
            requested_url='https://example.org/conference', raw_payload=self.payload)

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(reverse('candidate-review'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_view_permission_required(self):
        user = User.objects.create_user('no-permissions', password='test-only')
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('candidate-review')).status_code, 403)

    def test_page_and_static_assets(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('candidate-review'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Live AI candidates')
        self.assertContains(response, 'review-live.mjs')
        self.assertContains(response, 'approval/save integration pending')
        for asset in ['review.js', 'ai-client.mjs', 'review-live.mjs']:
            self.assertIsNotNone(finders.find('conferences/' + asset))

    def test_get_only_review_page(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse('candidate-review')).status_code, 405)

    def test_session_queue_and_detail_contract(self):
        self.client.force_login(self.user)
        session = self.client.get('/api/ai/session/').json()
        self.assertTrue(session['permissions']['view_candidates'])
        self.assertIn('csrf_token', session)
        queue = self.client.get('/api/ai/candidates/?status=needs_review').json()
        self.assertEqual(queue['results'][0]['id'], self.candidate.pk)
        detail = self.client.get(f'/api/ai/candidates/{self.candidate.pk}/').json()
        self.assertEqual(detail['payload'], self.payload)
        self.assertEqual(detail['status'], 'needs_review')
        self.assertEqual(ConferenceEdition.objects.count(), 0)

    @patch('conferences.ai_views.extract_and_stage')
    def test_extract_uses_csrf_then_returns_existing_candidate(self, extract):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        body = json.dumps({'url': 'https://example.org/conference', 'year': 2027, 'max_pages': 3})
        self.assertEqual(client.post('/api/ai/extract/', body, content_type='application/json').status_code, 403)
        extract.assert_not_called()
        session = client.get('/api/ai/session/').json()
        self.candidate._ai_created = False
        extract.return_value = self.candidate
        response = client.post('/api/ai/extract/', body, content_type='application/json',
                               HTTP_X_CSRFTOKEN=session['csrf_token'])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['created'])
        self.assertEqual(response.json()['payload'], self.payload)
        self.assertEqual(ConferenceEdition.objects.count(), 0)

    def test_current_status_comes_from_wrapper(self):
        self.candidate.status = ExtractionCandidate.Status.APPROVED
        self.candidate.save()
        self.client.force_login(self.user)
        detail = self.client.get(f'/api/ai/candidates/{self.candidate.pk}/').json()
        self.assertEqual(detail['status'], 'approved')
        self.assertEqual(detail['payload'], self.payload)
