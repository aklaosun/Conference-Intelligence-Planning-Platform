import os
from io import StringIO
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from .models import Conference


class SharedInitializationTests(TestCase):
    def environment(self,**overrides):
        values={'BOOTSTRAP_ADMIN_EMAIL':'owner@example.org','BOOTSTRAP_ADMIN_PASSWORD':'Unique-shared-bootstrap-Password-852!',
            'BOOTSTRAP_ADMIN_USERNAME':'workspace-admin','SEED_REAL_CATALOG':'1'}
        values.update(overrides)
        return patch.dict(os.environ,values)

    def test_first_start_seeds_real_catalog_and_private_owner(self):
        output=StringIO()
        with self.environment():call_command('initialize_shared',stdout=output)
        self.assertEqual(Conference.objects.count(),35)
        owner=User.objects.get(username='workspace-admin')
        self.assertTrue(owner.is_superuser)
        self.assertTrue(owner.check_password('Unique-shared-bootstrap-Password-852!'))
        self.assertNotIn('Unique-shared-bootstrap-Password-852!',output.getvalue())

    def test_restart_preserves_existing_records_and_password_without_bootstrap_secrets(self):
        with self.environment():call_command('initialize_shared',stdout=StringIO())
        owner=User.objects.get(username='workspace-admin');original=owner.password
        Conference.objects.create(name='Human added record')
        with self.environment(BOOTSTRAP_ADMIN_EMAIL='',BOOTSTRAP_ADMIN_PASSWORD=''):
            call_command('initialize_shared',stdout=StringIO())
        owner.refresh_from_db()
        self.assertEqual(owner.password,original);self.assertEqual(Conference.objects.count(),36)

    def test_missing_secrets_fail_before_inserting_data(self):
        with self.environment(BOOTSTRAP_ADMIN_PASSWORD=''):
            with self.assertRaises(CommandError):call_command('initialize_shared',stdout=StringIO())
        self.assertFalse(Conference.objects.exists());self.assertFalse(User.objects.exists())

    def test_weak_password_is_rejected(self):
        with self.environment(BOOTSTRAP_ADMIN_PASSWORD='123'):
            with self.assertRaises(CommandError):call_command('initialize_shared',stdout=StringIO())
        self.assertFalse(User.objects.exists())

    def test_existing_non_privileged_account_is_never_promoted(self):
        User.objects.create_user('workspace-admin')
        with self.environment():
            with self.assertRaises(CommandError):call_command('initialize_shared',stdout=StringIO())
        self.assertFalse(User.objects.get().is_superuser)

    def test_seed_is_opt_in(self):
        with self.environment(SEED_REAL_CATALOG='0'):call_command('initialize_shared',stdout=StringIO())
        self.assertFalse(Conference.objects.exists());self.assertEqual(User.objects.count(),1)
