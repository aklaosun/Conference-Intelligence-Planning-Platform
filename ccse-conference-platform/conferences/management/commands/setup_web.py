"""Repeatable local web initialization without fabricated team accounts."""
import json,secrets
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand,CommandError
from conferences.models import Conference


class Command(BaseCommand):
    help='Prepare the local browser workspace with real seed data and one private administrator.'

    def handle(self,*args,**options):
        if not getattr(settings,'WEB_WORKSPACE',False):
            raise CommandError('Use ccse_platform.web_settings. Shared servers must create their own administrator.')
        call_command('setup_platform',stdout=self.stdout)
        if not Conference.objects.exists():
            seed=Path(settings.BASE_DIR).parent/'data/demo-catalog.json'
            call_command('loaddata',str(seed),stdout=self.stdout)
        if not User.objects.filter(is_superuser=True,is_active=True).exists():
            username='workspace-admin'
            if User.objects.filter(username=username).exists():
                raise CommandError('workspace-admin already exists. Use createsuperuser to provision an administrator explicitly.')
            password=secrets.token_urlsafe(24)
            User.objects.create_superuser(username=username,password=password,first_name='Workspace',last_name='Administrator')
            login_file=settings.WEB_DATA_DIR/'admin-login.json'
            login_file.write_text(json.dumps({'username':username,'password':password,'note':'Private local setup login. Change the password in My account. Never share or upload this file.'},indent=2),encoding='utf-8')
            self.stdout.write('Private initial administrator login saved to .web-data/admin-login.json. Password was not printed.')
        self.stdout.write('Browser workspace ready. Existing data and account passwords were preserved.')
