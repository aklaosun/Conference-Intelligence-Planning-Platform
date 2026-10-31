from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = "Create an AI Researchers group with extraction and candidate-view permissions only."
    def handle(self, *args, **options):
        group, _ = Group.objects.get_or_create(name="AI Researchers")
        permissions = Permission.objects.filter(content_type__app_label="conferences",
            codename__in=["add_extractioncandidate","view_extractioncandidate"])
        if permissions.count() != 2:
            raise CommandError("Run Django migrations first.")
        group.permissions.add(*permissions)
        self.stdout.write("AI Researchers group configured. Assign users through Django admin; staff status is separate.")
