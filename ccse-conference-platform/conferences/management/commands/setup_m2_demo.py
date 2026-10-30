"""Prepare a local-only demo account and a captured real AI candidate."""
import json
import secrets
from pathlib import Path
from django.conf import settings
from django.contrib.auth.models import User,Group
from django.core.management import call_command
from django.core.management.base import BaseCommand,CommandError
from conferences.models import ExtractionCandidate

class Command(BaseCommand):
    help = "Set up the local M2 demo account and optional captured AI candidate; no external requests."
    def add_arguments(self,parser):
        parser.add_argument("--username",default="demo")
        parser.add_argument("--candidate-json")
        parser.add_argument("--new-review",action="store_true",help="Create an additional pending rehearsal copy without changing prior decisions.")
    def handle(self,*args,**options):
        if not settings.DEBUG:
            raise CommandError("Demo setup is restricted to development settings.")
        root=Path(settings.BASE_DIR).parent
        credentials_path=root/".m2-demo-login.json"
        call_command("setup_roles",stdout=self.stdout)
        call_command("configure_ai_role",stdout=self.stdout)
        username=options["username"]
        user=User.objects.filter(username=username).first()
        if user is None:
            password=secrets.token_urlsafe(15)
            user=User.objects.create_user(username=username,password=password,first_name="Demo",last_name="Reviewer")
            credentials_path.write_text(json.dumps({"username":username,"password":password,"url":"http://127.0.0.1:8010/"},indent=2),encoding="utf-8")
            self.stdout.write(f"Local demo login saved to {credentials_path.name} (ignored by Git).")
        user.groups.add(Group.objects.get(name="Reviewers"),Group.objects.get(name="AI Researchers"))
        source=Path(options["candidate_json"]) if options["candidate_json"] else root/"candidate-live.json"
        if not source.is_file():
            source=root/"examples/live-computing-frontiers-candidate.json"
        if source.is_file():
            payload=json.loads(source.read_text(encoding="utf-8-sig"))
            if not isinstance(payload,dict) or not isinstance(payload.get("fields"),dict) or not payload.get("requested_url"):
                raise CommandError("The captured candidate file is not a valid extraction.")
            extracted_at=payload.get("extracted_at")
            candidates=ExtractionCandidate.objects.filter(requested_url=payload["requested_url"])
            if extracted_at:
                candidates=candidates.filter(raw_payload__extracted_at=extracted_at)
            if options["new_review"] or not candidates.exists():
                candidate=ExtractionCandidate.objects.create(requested_url=payload["requested_url"],
                    schema_version=payload.get("schema_version","1.1"),raw_payload=payload)
                self.stdout.write(f"Prepared saved candidate #{candidate.pk} from the captured live extraction.")
        self.stdout.write("M2 demo is ready. Sign in with the local demo account.")

