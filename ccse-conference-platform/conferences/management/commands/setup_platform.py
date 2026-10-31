import json,secrets
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import User,Group,Permission
from django.core.management import call_command
from django.core.management.base import BaseCommand,CommandError
from conferences.planning_models import PlanningStage

class Command(BaseCommand):
    help='Configure workspace roles and planning stages; optionally prepare a local development owner.'
    def add_arguments(self,parser):parser.add_argument('--local-owner',action='store_true')
    def handle(self,*args,**opts):
        call_command('setup_roles',stdout=self.stdout)
        call_command('configure_ai_role',stdout=self.stdout)
        models=['conference','conferenceedition','deadline','registrationprice','extractioncandidate',
            'conferenceplan','budgetline','outcomereport','selectioncriterion','criterionrating','planningstage']
        read=Permission.objects.filter(content_type__app_label='conferences',content_type__model__in=models,codename__startswith='view_')
        view,_=Group.objects.get_or_create(name='Viewers');view.permissions.set(read)
        contribute,_=Group.objects.get_or_create(name='Contributors')
        contribute.permissions.set(list(read)+list(Permission.objects.filter(content_type__app_label='conferences',codename='add_extractioncandidate')))
        coordinate,_=Group.objects.get_or_create(name='Coordinators')
        coordinate.permissions.set(Permission.objects.filter(content_type__app_label='conferences',content_type__model__in=models))
        names=[('identified','Identified'),('under-evaluation','Under evaluation'),('interested','Interested'),
            ('tentatively-planned','Tentatively planned'),('approved','Approved'),('not-attending','Not attending'),('attended','Attended')]
        for position,(code,name) in enumerate(names):PlanningStage.objects.get_or_create(code=code,defaults={'name':name,'position':position})
        if opts['local_owner']:
            if not settings.DEBUG:raise CommandError('Local owner bootstrap is development-only.')
            username='workspace-owner'
            if not User.objects.filter(username=username).exists():
                password=secrets.token_urlsafe(20)
                User.objects.create_superuser(username=username,password=password,first_name='Workspace',last_name='Owner')
                path=Path(settings.BASE_DIR).parent/'.m2-owner-login.json'
                path.write_text(json.dumps({'username':username,'password':password,'url':'http://127.0.0.1:8010/app/'},indent=2),encoding='utf-8')
                self.stdout.write('Private local owner login saved to .m2-owner-login.json.')
        self.stdout.write('Workspace roles and planning stages are ready. No attendee decisions or evaluation weights were created.')
