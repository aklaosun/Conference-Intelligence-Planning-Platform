from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from conferences.permissions import EDITORS, REVIEWERS

EDIT_MODELS = ["conference", "conferenceedition", "deadline", "registrationprice"]


class Command(BaseCommand):
    help = "Create the Reviewers and Editors groups with their permissions"

    def handle(self, *args, **options):
        edit_perms = Permission.objects.filter(
            content_type__app_label="conferences",
            content_type__model__in=EDIT_MODELS,
            codename__regex=r"^(add|change|delete|view)_",
        )
        candidate_perms = Permission.objects.filter(
            content_type__app_label="conferences",
            content_type__model="extractioncandidate",
        )

        editors, _ = Group.objects.get_or_create(name=EDITORS)
        editors.permissions.set(edit_perms)

        reviewers, _ = Group.objects.get_or_create(name=REVIEWERS)
        reviewers.permissions.set(list(edit_perms) + list(candidate_perms))

        self.stdout.write(self.style.SUCCESS(f"Groups ready: {EDITORS}, {REVIEWERS}"))
