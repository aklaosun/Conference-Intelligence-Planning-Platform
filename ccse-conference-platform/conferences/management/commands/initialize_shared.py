"""Seed public source data and bootstrap an explicitly configured private owner."""
import os
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand,CommandError
from django.core.validators import validate_email
from django.db import transaction
from conferences.models import Conference


class Command(BaseCommand):
    help='Initialize a shared deployment without copying local passwords or overwriting existing data.'

    def handle(self,*args,**options):
        existing_admin=User.objects.filter(is_superuser=True,is_active=True).exists()
        username=os.environ.get('BOOTSTRAP_ADMIN_USERNAME','workspace-admin').strip()
        email=os.environ.get('BOOTSTRAP_ADMIN_EMAIL','').strip().lower()
        password=os.environ.get('BOOTSTRAP_ADMIN_PASSWORD','')
        if not existing_admin:
            if not email or not password:
                raise CommandError('First deployment requires private BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD environment variables.')
            candidate=User(username=username,email=email,is_superuser=True,is_staff=True)
            try:
                candidate.full_clean(exclude=['password'])
                validate_email(email)
                validate_password(password,candidate)
            except ValidationError:
                raise CommandError('Bootstrap administrator details are invalid or the password is too weak. Use a valid email, unused username, and strong unique password.') from None
        with transaction.atomic():
            if os.environ.get('SEED_REAL_CATALOG','0')=='1' and not Conference.objects.exists():
                seed=Path(settings.BASE_DIR).parent/'data/demo-catalog.json'
                call_command('loaddata',str(seed),stdout=self.stdout)
            if not existing_admin:
                User.objects.create_superuser(username=username,email=email,password=password,first_name='Workspace',last_name='Administrator')
                self.stdout.write('Initial shared administrator created. Credentials were not printed.')
        self.stdout.write('Shared initialization complete. Existing records and passwords were preserved.')
