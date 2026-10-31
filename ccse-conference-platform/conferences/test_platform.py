import json
from decimal import Decimal
from io import StringIO
from django.contrib.auth.models import User,Group
from django.core.management import call_command
from django.test import TestCase,Client,override_settings
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
import os,csv
from django.utils import timezone
from .models import Conference,ConferenceEdition,Deadline
from .planning_models import (PlanningStage,ConferencePlan,BudgetLine,SelectionCriterion,CriterionRating,
    OutcomeReport,ActivityEvent,budget_totals,evaluation_scores)
from .access_models import AccessInvitation

class WorkspaceTests(TestCase):
    def setUp(self):
        call_command('setup_platform',stdout=StringIO())
        self.owner=User.objects.create_superuser('owner',password='Test-password-for-owner-123')
        self.viewer=User.objects.create_user('viewer',password='Test-password-for-viewer-123')
        self.viewer.groups.add(Group.objects.get(name='Viewers'))
        self.coordinator=User.objects.create_user('coordinator',password='Test-password-for-coordinator-123')
        self.coordinator.groups.add(Group.objects.get(name='Coordinators'))
        self.contributor=User.objects.create_user('contributor',password='Test-password-for-contributor-123')
        self.contributor.groups.add(Group.objects.get(name='Contributors'))
        self.conference=Conference.objects.create(name='Real Conference',cac_relevant=True)
        self.edition=ConferenceEdition.objects.create(conference=self.conference,year=2027,location='Source city')
        self.stage=PlanningStage.objects.get(code='identified')
        self.client.force_login(self.coordinator)
    def post(self,url,data,client=None):
        return (client or self.client).post('/api/platform/'+url,data=json.dumps(data),content_type='application/json')
    def plan_packet(self,lines=None):
        return {'plan':{'stage':self.stage.pk,'owner':self.coordinator.pk,'objective':'Research partnerships','notes':''},
            'budget_lines':lines or []}
    def line(self,**overrides):
        value={'category':'registration','description':'Published fee','currency':'EUR','estimated':'650.00','actual':None,'source_url':'https://example.org/registration'}
        value.update(overrides);return value
    def test_anonymous_api_has_json_401(self):
        self.client.logout()
        self.assertEqual(self.client.get('/api/platform/overview/').status_code,401)
    def test_session_bootstraps_csrf_without_authentication(self):
        response=Client().get('/api/platform/session/')
        self.assertFalse(response.json()['authenticated']);self.assertTrue(response.json()['csrf_token'])
    def test_login_is_csrf_protected_and_rotates_token(self):
        client=Client(enforce_csrf_checks=True)
        token=client.get('/api/platform/session/').json()['csrf_token']
        self.assertEqual(self.post('login/',{'username':'viewer','password':'Test-password-for-viewer-123'},client).status_code,403)
        response=client.post('/api/platform/login/',data=json.dumps({'username':'viewer','password':'Test-password-for-viewer-123'}),content_type='application/json',HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code,200);self.assertTrue(response.json()['authenticated'])
        self.assertNotEqual(token,response.json()['csrf_token'])
    def test_repeated_bad_login_is_throttled(self):
        client=Client()
        for _ in range(8):self.assertEqual(self.post('login/',{'username':'bad','password':'wrong'},client).status_code,400)
        self.assertEqual(self.post('login/',{'username':'bad','password':'wrong'},client).status_code,429)
    def test_catalog_search_and_unknown_dates(self):
        result=self.client.get('/api/platform/catalog/?q=Real').json()
        self.assertEqual(result['count'],1)
        self.assertIsNone(result['results'][0]['editions'][0]['start_date'])
    def test_viewer_can_read_but_cannot_plan_research_or_manage_people(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get('/api/platform/plans/').status_code,200)
        self.assertEqual(self.post(f'plans/{self.edition.pk}/',self.plan_packet()).status_code,403)
        self.assertEqual(self.post('team/',{'action':'invite','email':'test@example.org','role':'coordinator'}).status_code,403)
        self.assertFalse(self.client.get('/api/platform/session/').json()['user']['can_research'])
    def test_contributor_can_research_but_not_approve_or_edit(self):
        self.client.force_login(self.contributor)
        role=self.client.get('/api/platform/session/').json()['user']
        self.assertTrue(role['can_research']);self.assertFalse(role['can_review']);self.assertFalse(role['can_edit'])
    def test_planning_with_unknown_and_separate_currencies(self):
        response=self.post(f'plans/{self.edition.pk}/',self.plan_packet([
            self.line(),self.line(category='travel',description='Travel estimate not yet known',estimated=None),
            self.line(description='USD lodging',currency='USD',estimated='200.00')]))
        self.assertEqual(response.status_code,200,response.content)
        totals={t['currency']:t for t in response.json()['totals']}
        self.assertEqual(totals['EUR']['estimated_known'],'650.00')
        self.assertIsNone(totals['EUR']['estimated_total'])
        self.assertEqual(totals['USD']['estimated_total'],'200.00')
        self.assertEqual(ActivityEvent.objects.filter(action='plan_updated').count(),1)
    def test_explicit_zero_survives_and_negative_cost_does_not(self):
        url=f'plans/{self.edition.pk}/'
        self.assertEqual(self.post(url,self.plan_packet([self.line(estimated='0')])).status_code,200)
        self.assertEqual(BudgetLine.objects.get().estimated,Decimal('0'))
        self.assertEqual(self.post(url,self.plan_packet([self.line(estimated='-1')])).status_code,400)
        self.assertEqual(BudgetLine.objects.get().estimated,Decimal('0'))
    def test_saved_budget_ids_are_returned_and_removed_rows_are_retained_inactive(self):
        url=f'plans/{self.edition.pk}/'
        result=self.post(url,self.plan_packet([self.line()])).json()
        line_id=result['budget_lines'][0]['id']
        self.assertIsInstance(line_id,int)
        self.assertEqual(self.post(url,self.plan_packet([])).status_code,200)
        self.assertFalse(BudgetLine.objects.get(pk=line_id).active)
    def test_cannot_edit_another_plans_budget_line(self):
        other=ConferenceEdition.objects.create(conference=self.conference,year=2028)
        plan=ConferencePlan.objects.create(edition=other,stage=self.stage)
        line=BudgetLine.objects.create(plan=plan,category='travel',description='Other plan',currency='USD',estimated=100)
        result=self.post(f'plans/{self.edition.pk}/',self.plan_packet([self.line(id=line.pk)]))
        self.assertEqual(result.status_code,400)
        self.assertFalse(ConferencePlan.objects.filter(edition=self.edition).exists())
    def test_outcome_and_follow_up_are_persisted(self):
        response=self.post(f'outcomes/{self.edition.pk}/',{'summary':'Documented collaboration follow-up','attendees':0,'contacts':3,
            'partnerships':None,'follow_up':'Schedule a discussion','follow_up_date':'2027-06-01','follow_up_completed':False})
        self.assertEqual(response.status_code,200,response.content)
        report=OutcomeReport.objects.get();self.assertEqual(report.attendees,0);self.assertIsNone(report.partnerships)
        self.assertEqual(len(self.client.get('/api/platform/deadlines/').json()['follow_ups']),1)
    def test_no_score_without_approved_criteria_and_all_ratings(self):
        criterion=SelectionCriterion.objects.create(center='CAC',name='Sponsor criterion',weight=50,approved=False)
        CriterionRating.objects.create(edition=self.edition,criterion=criterion,rating=4,rationale='Source-backed rationale')
        self.assertIsNone(evaluation_scores(self.edition)[0]['score'])
        criterion.approved=True;criterion.save()
        self.assertEqual(evaluation_scores(self.edition)[0]['score'],Decimal('80.0'))
        SelectionCriterion.objects.create(center='CAC',name='Second criterion',weight=50,approved=True)
        self.assertIsNone(evaluation_scores(self.edition)[0]['score'])
    def test_approved_criterion_requires_a_weight_and_admin(self):
        data={'center':'CAC','name':'Criterion','description':'Agreed guidance','weight':None,'approved':True,'active':True}
        self.assertEqual(self.post('criteria/',data).status_code,403)
        self.client.force_login(self.owner)
        self.assertEqual(self.post('criteria/',data).status_code,400)
    def test_inactive_deadlines_are_not_exposed(self):
        Deadline.objects.create(edition=self.edition,type='active',date=timezone.localdate(),is_active=True)
        Deadline.objects.create(edition=self.edition,type='inactive',date=timezone.localdate(),is_active=False)
        self.assertEqual([d['type'] for d in self.client.get('/api/platform/deadlines/').json()['results']],['active'])
    def test_invitation_token_is_hashed_single_use_and_fixes_the_role(self):
        self.client.force_login(self.owner)
        response=self.post('team/',{'email':'sponsor@example.org','role':'viewer'})
        self.assertEqual(response.status_code,200,response.content)
        token=response.json()['invitation_url'].split('/join/')[1]
        record=AccessInvitation.objects.get()
        self.assertNotEqual(token,record.token_hash)
        guest=Client()
        result=self.post(f'invitations/{token}/',{'username':'sponsor','password1':'Strong-test-password-2890','password2':'Strong-test-password-2890','role':'coordinator'},guest)
        self.assertEqual(result.status_code,200,result.content)
        user=User.objects.get(username='sponsor')
        self.assertTrue(user.groups.filter(name='Viewers').exists());self.assertFalse(user.is_staff)
        self.assertEqual(guest.get(f'/api/platform/invitations/{token}/').status_code,410)
    def test_expired_and_revoked_invitations_cannot_be_accepted(self):
        invitation,token=AccessInvitation.issue(email='x@example.org',role='viewer',user=self.owner)
        invitation.expires_at=timezone.now()-timezone.timedelta(seconds=1);invitation.save()
        self.assertEqual(Client().get(f'/api/platform/invitations/{token}/').status_code,410)
    def test_admin_cannot_disable_itself_or_grant_administrator_via_role_input(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.post('team/',{'action':'active','id':self.owner.pk,'active':False}).status_code,400)
        self.assertEqual(self.post('team/',{'action':'role','id':self.viewer.pk,'role':'administrator'}).status_code,400)
        self.owner.refresh_from_db();self.assertTrue(self.owner.is_active)

    def test_review_can_embed_only_on_the_same_origin(self):
        response=self.client.get('/review/workbench/?embedded=1')
        self.assertEqual(response['X-Frame-Options'],'SAMEORIGIN')
        self.assertContains(response,'data-embedded="true"')

    def test_local_bootstrap_is_unavailable_on_normal_servers(self):
        self.assertEqual(self.post('desktop-bootstrap/',{}).status_code,404)

    @override_settings(LOCAL_DESKTOP=True)
    def test_local_bootstrap_is_loopback_only_and_single_use(self):
        User.objects.create_superuser('desktop-owner',password='Test local owner password')
        guest=Client(enforce_csrf_checks=True)
        with patch.dict(os.environ,{'CCSE_DESKTOP_BOOTSTRAP_TOKEN':'launch-token-with-sufficient-entropy'}):
            self.assertEqual(guest.post('/api/platform/desktop-bootstrap/',HTTP_X_DESKTOP_BOOTSTRAP='wrong').status_code,403)
            self.assertEqual(guest.post('/api/platform/desktop-bootstrap/',REMOTE_ADDR='192.0.2.5',HTTP_X_DESKTOP_BOOTSTRAP='launch-token-with-sufficient-entropy').status_code,403)
            self.assertEqual(guest.post('/api/platform/desktop-bootstrap/',HTTP_X_DESKTOP_BOOTSTRAP='launch-token-with-sufficient-entropy').status_code,200)
            self.assertEqual(guest.post('/api/platform/desktop-bootstrap/',HTTP_X_DESKTOP_BOOTSTRAP='launch-token-with-sufficient-entropy').status_code,403)
        self.assertTrue(guest.get('/api/platform/session/').json()['authenticated'])

    def test_local_key_settings_never_return_the_key(self):
        self.client.force_login(self.owner)
        with TemporaryDirectory() as folder:
            config=Path(folder)/'backend.env'
            with override_settings(LOCAL_DESKTOP=True,DESKTOP_DATA_DIR=Path(folder),DESKTOP_CONFIG=config),patch.dict(os.environ,{},clear=False):
                key='AIza-test-only-fake-key-not-a-real-credential'
                response=self.post('local-settings/',{'api_key':key,'model':'gemini-3.5-flash-lite'})
                self.assertEqual(response.status_code,200)
                self.assertNotIn(key,response.content.decode())
                self.assertIn(key,config.read_text())
                self.assertEqual(self.post('local-settings/',{'api_key':'bad\nINJECT=value','model':'gemini-3.5-flash-lite'}).status_code,400)
                self.assertEqual(config.read_text().count('GEMINI_API_KEY='),1)

    def test_planning_csv_keeps_unknowns_and_formula_cells_safe(self):
        self.conference.name='=HYPERLINK("https://example.org")';self.conference.save()
        self.post(f'plans/{self.edition.pk}/',self.plan_packet([self.line(estimated=None,actual=None)]))
        response=self.client.get('/api/platform/reports/export/')
        row=list(csv.DictReader(StringIO(response.content.decode())))[0]
        self.assertTrue(row['Conference'].startswith("'="))
        self.assertEqual(row['Estimated total'],'');self.assertEqual(row['Known estimated subtotal'],'')
        self.assertEqual(row['Actual cost per attendee'],'')

    def test_outcomes_without_a_plan_are_included_in_csv(self):
        OutcomeReport.objects.create(edition=self.edition,summary='Recorded outcome without a planning record',contacts=0)
        rows=list(csv.DictReader(StringIO(self.client.get('/api/platform/reports/export/').content.decode())))
        self.assertEqual(rows[0]['Contacts'],'0');self.assertEqual(rows[0]['Planning status'],'Not planned')

    def test_email_is_opt_in_and_weekly_retry_does_not_resend(self):
        from django.core import mail
        from .planning_models import ReportSubscription
        ReportSubscription.objects.create(name='Test director',email='director@example.org',enabled=True,weekday=timezone.localdate().weekday())
        call_command('send_weekly_reports',stdout=StringIO())
        with override_settings(WORKSPACE_EMAIL_ENABLED=True,EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',DEFAULT_FROM_EMAIL='demo@example.org'):
            call_command('send_weekly_reports',send=True,stdout=StringIO())
            call_command('send_weekly_reports',send=True,stdout=StringIO())
            self.assertEqual(len(mail.outbox),1)
            self.assertEqual(mail.outbox[0].attachments[0][0],'conference-planning-outcomes.csv')

    def test_ai_approval_matches_a_spreadsheet_label_by_website(self):
        from .test_integration import pending_candidate
        from .approval_service import approve_candidate
        candidate=pending_candidate()
        self.conference.website=candidate.requested_url;self.conference.save()
        approved=approve_candidate(candidate,reviewer='Test reviewer')
        self.assertEqual(approved.conference_id,self.conference.pk)
        self.assertEqual(Conference.objects.count(),1)
