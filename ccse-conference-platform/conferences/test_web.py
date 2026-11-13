import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
from django.contrib.auth.models import User,Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase,Client,override_settings
from .models import Conference,ConferenceEdition,AccessInvitation,UserPreference


class WebAccountTests(TestCase):
    def setUp(self):
        call_command('setup_platform',stdout=StringIO())
        self.users={}
        for role,group in [('viewer','Viewers'),('contributor','Contributors'),('coordinator','Coordinators'),('administrator','Administrators')]:
            user=User.objects.create_user(role,password='Initial-Password-734!')
            user.groups.add(Group.objects.get(name=group));self.users[role]=user
        self.owner=User.objects.create_superuser('owner',password='Owner-Password-734!')
        self.client.force_login(self.users['administrator'])

    def post(self,path,data,client=None):
        return (client or self.client).post('/api/platform/'+path,json.dumps(data),content_type='application/json')

    def test_root_opens_browser_workspace(self):
        self.assertRedirects(self.client.get('/'),'/app/',fetch_redirect_response=False)

    def test_group_administrator_manages_users_without_django_staff_access(self):
        response=self.client.get('/api/platform/team/')
        self.assertEqual(response.status_code,200)
        self.assertFalse(self.users['administrator'].is_staff)
        self.assertEqual(self.client.get('/admin/').status_code,302)
        role=self.client.get('/api/platform/session/').json()['user']
        self.assertTrue(role['is_admin']);self.assertTrue(role['can_edit']);self.assertTrue(role['can_research'])
        self.assertEqual(role['role'],'administrator')

    def test_other_roles_cannot_manage_members_or_criteria(self):
        for role in ['viewer','contributor','coordinator']:
            self.client.force_login(self.users[role])
            self.assertEqual(self.client.get('/api/platform/team/').status_code,403)
            self.assertEqual(self.post('criteria/',{'name':'Unauthorized'}).status_code,403)
            self.assertEqual(self.client.get('/api/platform/subscriptions/').status_code,403)

    def test_role_matrix_matches_server_permissions(self):
        expected={'viewer':(False,False,False),'contributor':(False,False,True),'coordinator':(True,True,True),'administrator':(True,True,True)}
        for role,flags in expected.items():
            self.client.force_login(self.users[role])
            user=self.client.get('/api/platform/session/').json()['user']
            self.assertEqual((user['can_edit'],user['can_review'],user['can_research']),flags)

    def test_invitation_accepts_full_name_and_selected_administrator_role(self):
        response=self.post('team/',{'action':'invite','email':'new-admin@example.org','role':'administrator'})
        self.assertEqual(response.status_code,200,response.content)
        token=response.json()['invitation_url'].rsplit('/',1)[-1]
        guest=Client()
        response=self.post(f'invitations/{token}/',{'username':'new-admin','first_name':'New','last_name':'Member','password1':'Different-Strong-Pass-833!','password2':'Different-Strong-Pass-833!'},guest)
        self.assertEqual(response.status_code,200,response.content)
        user=User.objects.get(username='new-admin')
        self.assertEqual(user.get_full_name(),'New Member');self.assertFalse(user.is_staff);self.assertFalse(user.is_superuser)
        self.assertEqual(guest.get('/api/platform/team/').status_code,200)
        self.assertEqual(guest.get('/api/platform/invitations/'+token+'/').status_code,410)

    def test_role_downgrade_immediately_changes_access(self):
        target=self.users['coordinator']
        response=self.post('team/',{'action':'role','id':target.pk,'role':'viewer'})
        self.assertEqual(response.status_code,200)
        self.client.force_login(target)
        user=self.client.get('/api/platform/session/').json()['user']
        self.assertFalse(user['can_edit']);self.assertFalse(user['can_review']);self.assertFalse(user['can_research'])

    def test_own_and_root_accounts_cannot_be_disabled_or_demoted(self):
        for user in [self.users['administrator'],self.owner]:
            self.assertEqual(self.post('team/',{'action':'active','id':user.pk,'active':False}).status_code,400)
            self.assertEqual(self.post('team/',{'action':'role','id':user.pk,'role':'viewer'}).status_code,400)

    def test_disabled_account_loses_its_existing_session(self):
        guest=Client();guest.force_login(self.users['viewer'])
        response=self.post('team/',{'action':'active','id':self.users['viewer'].pk,'active':False})
        self.assertEqual(response.status_code,200)
        self.assertEqual(guest.get('/api/platform/alerts/').status_code,401)

    def test_theme_is_saved_for_only_the_current_user_and_survives_login(self):
        for theme in ['ksu','light','dark','midnight']:
            result=self.post('account/',{'action':'theme','theme':theme,'user_id':self.owner.pk})
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.json()['user']['theme'],theme)
        self.assertFalse(UserPreference.objects.filter(user=self.owner).exists())
        self.client.logout();self.client.force_login(self.users['administrator'])
        self.assertEqual(self.client.get('/api/platform/session/').json()['user']['theme'],'midnight')

    def test_unknown_theme_and_account_actions_are_rejected(self):
        self.assertEqual(self.post('account/',{'action':'theme','theme':'javascript:alert(1)'}).status_code,400)
        self.assertEqual(self.post('account/',{'action':'make-admin'}).status_code,400)

    def test_profile_updates_do_not_escalate_role_or_change_other_users(self):
        self.client.force_login(self.users['viewer'])
        result=self.post('account/',{'action':'profile','first_name':'Test','last_name':'Viewer','email':'viewer@example.org','is_superuser':True,'user_id':self.owner.pk})
        self.assertEqual(result.status_code,200,result.content)
        user=User.objects.get(pk=self.users['viewer'].pk)
        self.assertEqual(user.get_full_name(),'Test Viewer');self.assertFalse(user.is_superuser)
        self.assertEqual(self.client.get('/api/platform/team/').status_code,403)

    def test_password_change_validates_old_password_and_preserves_current_session(self):
        user=self.users['viewer'];self.client.force_login(user)
        data={'action':'password','old_password':'incorrect','new_password1':'Updated-Password-852!','new_password2':'Updated-Password-852!'}
        self.assertEqual(self.post('account/',data).status_code,400)
        data['old_password']='Initial-Password-734!'
        response=self.post('account/',data)
        self.assertEqual(response.status_code,200,response.content)
        user.refresh_from_db();self.assertTrue(user.check_password('Updated-Password-852!'))
        self.assertTrue(self.client.get('/api/platform/session/').json()['authenticated'])

    def test_profile_and_theme_changes_require_authentication_and_csrf(self):
        self.client.logout();self.assertEqual(self.client.get('/api/platform/account/').status_code,401)
        guest=Client(enforce_csrf_checks=True);guest.force_login(self.users['viewer'])
        self.assertEqual(self.post('account/',{'action':'theme','theme':'light'},guest).status_code,403)

    def test_embedded_review_and_browser_app_load_theme_styles(self):
        for path in ['/app/','/review/workbench/?embedded=1']:
            response=self.client.get(path)
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'conferences/theme-palette.css')

    def test_local_web_ai_settings_are_admin_only_and_never_return_key(self):
        with TemporaryDirectory() as folder,override_settings(LOCAL_DESKTOP=False,WEB_WORKSPACE=True,WEB_DATA_DIR=Path(folder),WEB_AI_CONFIG=Path(folder)/'backend.env'),patch.dict(os.environ,{},clear=False):
            self.client.force_login(self.users['viewer'])
            self.assertEqual(self.client.get('/api/platform/local-settings/').status_code,403)
            self.client.force_login(self.users['administrator'])
            key='QA-only-not-a-real-provider-key-381'
            response=self.post('local-settings/',{'api_key':key,'model':'gemini-3.5-flash-lite'})
            self.assertEqual(response.status_code,200,response.content)
            self.assertNotIn(key,response.content.decode())
            self.assertIn(key,(Path(folder)/'backend.env').read_text())

    def test_shared_host_ai_settings_use_environment_not_local_configuration_api(self):
        with override_settings(LOCAL_DESKTOP=False,WEB_WORKSPACE=False):
            self.assertEqual(self.client.get('/api/platform/local-settings/').status_code,404)


class WebSetupTests(TestCase):
    def test_local_setup_is_repeatable_and_preserves_private_password_and_real_seed(self):
        with TemporaryDirectory() as folder,override_settings(WEB_WORKSPACE=True,WEB_DATA_DIR=Path(folder)):
            call_command('setup_web',stdout=StringIO())
            user=User.objects.get(username='workspace-admin')
            password_hash=user.password
            login=Path(folder)/'admin-login.json'
            self.assertTrue(login.exists());self.assertEqual(Conference.objects.count(),35)
            call_command('setup_web',stdout=StringIO())
            user.refresh_from_db();self.assertEqual(user.password,password_hash)
            self.assertEqual(Conference.objects.count(),35)

    def test_local_setup_cannot_run_on_shared_settings(self):
        with override_settings(WEB_WORKSPACE=False):
            with self.assertRaises(CommandError):call_command('setup_web',stdout=StringIO())
