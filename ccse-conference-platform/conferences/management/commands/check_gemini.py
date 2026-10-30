from django.core.management.base import BaseCommand, CommandError
from conferences.ai_service import GeminiProvider, ExtractionError

class Command(BaseCommand):
    help = "Check Gemini credentials and configured model without generating content."
    def handle(self, *args, **options):
        try:
            model = GeminiProvider().check_access()
        except ExtractionError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(self.style.SUCCESS(f"Gemini connection OK. Configured model available: {model}"))
