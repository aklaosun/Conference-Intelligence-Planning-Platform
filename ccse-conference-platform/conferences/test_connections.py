import base64
from io import StringIO
import json
from unittest.mock import Mock, patch
import requests
from django.contrib.auth.models import User
from django.core import mail
from django.core.mail import EmailMessage
from django.core.management import call_command
from django.test import TestCase, SimpleTestCase, Client, override_settings
from django.utils import timezone
from .email_backend import BrevoEmailBackend, EmailDeliveryError
from .planning_models import ReportSubscription, ReportDelivery


@override_settings(WORKSPACE_EMAIL_ENABLED=True, BREVO_API_KEY='unit-test-private-key')
class BrevoBackendTests(SimpleTestCase):
    @patch('conferences.email_backend.requests.post')
    def test_csv_and_utf8_content_use_https_and_private_header(self, post):
        post.return_value = Mock(status_code=201, json=lambda: {'messageId':'accepted-test'})
        message=EmailMessage('Weekly report', 'Hello — team', 'CCSE <sender@example.org>', ['reader@example.org'],
            headers={'IdempotencyKey':'report-4-week'})
        message.attach('report.csv','Conference,Year\r\nReal,2027\r\n','text/csv')
        self.assertEqual(BrevoEmailBackend().send_messages([message]),1)
        args,kwargs=post.call_args
        self.assertEqual(args[0],'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(kwargs['headers']['api-key'],'unit-test-private-key')
        self.assertFalse(kwargs['allow_redirects'])
        self.assertEqual(kwargs['json']['sender'],{'name':'CCSE','email':'sender@example.org'})
        self.assertEqual(kwargs['json']['headers']['IdempotencyKey'],'report-4-week')
        self.assertEqual(base64.b64decode(kwargs['json']['attachment'][0]['content']).decode(),'Conference,Year\r\nReal,2027\r\n')

    @patch('conferences.email_backend.requests.post')
    def test_provider_rejection_never_leaks_response_or_key(self, post):
        post.return_value=Mock(status_code=401,text='unit-test-private-key recipient@example.org')
        with self.assertRaises(EmailDeliveryError) as failure:
            BrevoEmailBackend().send_messages([EmailMessage('Test','Hello','sender@example.org',['reader@example.org'])])
        self.assertNotIn('unit-test-private-key',str(failure.exception))
        self.assertNotIn('recipient@example.org',str(failure.exception))

    @patch('conferences.email_backend.requests.post',side_effect=requests.Timeout('private details'))
    def test_timeout_has_no_automatic_send_retry(self, post):
        with self.assertRaises(EmailDeliveryError):
            BrevoEmailBackend().send_messages([EmailMessage('Test','Hi','sender@example.org',['reader@example.org'])])
        self.assertEqual(post.call_count,1)

    @patch('conferences.email_backend.requests.post')
    def test_missing_acceptance_identifier_is_failure(self, post):
        post.return_value=Mock(status_code=201,json=lambda:{})
        with self.assertRaises(EmailDeliveryError):
            BrevoEmailBackend().send_messages([EmailMessage('Test','Hi','sender@example.org',['reader@example.org'])])

    @override_settings(WORKSPACE_EMAIL_ENABLED=False)
    @patch('conferences.email_backend.requests.post')
    def test_disabled_email_never_transmits(self, post):
        self.assertEqual(BrevoEmailBackend(fail_silently=True).send_messages([
            EmailMessage('Test','Hi','sender@example.org',['reader@example.org'])]),0)
        post.assert_not_called()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='CCSE <sender@example.org>', WORKSPACE_EMAIL_ENABLED=True,
    REPORT_JOB_TOKEN='only-for-tests-'+'x'*60)
class HostedConnectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_platform',stdout=StringIO())
        cls.owner=User.objects.create_superuser('connection-admin',email='admin@example.org',password='Unit-test-password-927!')
        cls.viewer=User.objects.create_user('connection-viewer',email='viewer@example.org')

    def setUp(self):
        self.client.force_login(self.owner)

    def post(self,path,data,client=None):
        return (client or self.client).post('/api/platform/'+path+'/',json.dumps(data),content_type='application/json')

    def test_connections_require_admin(self):
        self.assertEqual(Client().get('/api/platform/connections/').status_code,401)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get('/api/platform/connections/').status_code,403)
        self.assertEqual(self.post('connections',{'action':'test_email'}).status_code,403)
        self.assertEqual(len(mail.outbox),0)

    @patch.dict('os.environ',{'GEMINI_API_KEY':'unit-test-private-gemini-key'})
    def test_status_reports_presence_without_secrets(self):
        response=self.client.get('/api/platform/connections/')
        self.assertTrue(response.json()['gemini_configured'])
        self.assertNotContains(response,'unit-test-private-gemini-key')
        self.assertNotContains(response,'only-for-tests-')

    def test_email_test_only_sends_to_requesting_administrator(self):
        response=self.post('connections',{'action':'test_email','email':'unapproved@example.org'})
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(mail.outbox[0].to,['admin@example.org'])
        self.assertIn('accepted',response.json()['message'])

    @patch('conferences.connection_views.send_mail',side_effect=RuntimeError('secret-key details'))
    def test_test_email_failure_is_not_reported_as_success(self, send):
        response=self.post('connections',{'action':'test_email'})
        self.assertEqual(response.status_code,502)
        self.assertNotContains(response,'secret-key',status_code=502)

    @patch('conferences.connection_views.GeminiProvider')
    def test_gemini_check_lists_model_without_extraction(self, provider):
        provider.return_value.check_access.return_value='gemini-test-model'
        response=self.post('connections',{'action':'check_gemini'})
        self.assertEqual(response.status_code,200)
        provider.return_value.extract.assert_not_called()

    def test_connection_posts_keep_csrf_protection(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(self.post('connections',{'action':'test_email'},client).status_code,403)

    def test_invitation_email_requires_explicit_selection(self):
        response=self.post('team',{'action':'invite','email':'manual@example.org','role':'viewer'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(mail.outbox),0)
        response=self.post('team',{'action':'invite','email':'invited@example.org','role':'viewer','send_email':True})
        self.assertEqual(response.status_code,200,response.content)
        self.assertTrue(response.json()['email_sent'])
        self.assertIn(response.json()['invitation_url'],mail.outbox[0].body)

    @patch('django.core.mail.send_mail',side_effect=RuntimeError('secret-key details'))
    def test_invitation_failure_preserves_manual_link(self, send):
        response=self.post('team',{'action':'invite','email':'fallback@example.org','role':'viewer','send_email':True})
        self.assertEqual(response.status_code,200,response.content)
        self.assertTrue(response.json()['invitation_url'])
        self.assertFalse(response.json()['email_sent'])
        self.assertTrue(response.json()['email_warning'])
        self.assertNotContains(response,'secret-key')

    def job(self,token=None):
        client=Client(enforce_csrf_checks=True)
        kwargs={'HTTP_AUTHORIZATION':'Bearer '+token} if token else {}
        return client.post('/api/platform/scheduled-reports/',**kwargs)

    def test_scheduler_denies_unauthorized_requests_and_get(self):
        self.assertEqual(self.job().status_code,401)
        self.assertEqual(self.job('wrong-token').status_code,401)
        self.assertEqual(self.client.get('/api/platform/scheduled-reports/').status_code,405)

    @override_settings(REPORT_JOB_TOKEN='short')
    def test_scheduler_fails_closed_with_short_token(self):
        self.assertEqual(self.job('short').status_code,401)

    def test_due_reports_send_once_and_only_to_enabled_subscribers(self):
        today=timezone.localdate()
        ReportSubscription.objects.create(name='Approved',email='approved@example.org',enabled=True,weekday=today.weekday())
        ReportSubscription.objects.create(name='Disabled',email='disabled@example.org',enabled=False,weekday=today.weekday())
        ReportSubscription.objects.create(name='Other day',email='later@example.org',enabled=True,weekday=(today.weekday()+1)%7)
        first=self.job('only-for-tests-'+'x'*60)
        second=self.job('only-for-tests-'+'x'*60)
        self.assertEqual(first.json(),{'accepted':1})
        self.assertEqual(second.json(),{'accepted':0})
        self.assertEqual(len(mail.outbox),1)
        self.assertEqual(mail.outbox[0].to,['approved@example.org'])
        self.assertEqual(mail.outbox[0].attachments[0][0],'conference-planning-outcomes.csv')
        self.assertTrue(mail.outbox[0].extra_headers['IdempotencyKey'].startswith('ccse-weekly-'))

    @patch('conferences.report_delivery.EmailMessage.send',side_effect=RuntimeError('private-key'))
    def test_failed_report_can_be_retried_without_false_delivery_record(self, send):
        ReportSubscription.objects.create(name='Approved',email='approved@example.org',enabled=True,weekday=timezone.localdate().weekday())
        response=self.job('only-for-tests-'+'x'*60)
        self.assertEqual(response.status_code,502)
        self.assertEqual(ReportDelivery.objects.filter(sent_at__isnull=False).count(),0)
        self.assertNotContains(response,'private-key',status_code=502)
