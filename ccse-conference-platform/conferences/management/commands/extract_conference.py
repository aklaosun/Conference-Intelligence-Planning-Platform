import json
from pathlib import Path
import requests
from django.core.management.base import BaseCommand, CommandError
from conferences.ai_service import ExtractionError
from conferences.research_service import research_and_stage

class Command(BaseCommand):
    help = "Research a conference and bounded companion pages; stage an evidence-backed candidate."
    def add_arguments(self, parser):
        parser.add_argument("url")
        parser.add_argument("--year", type=int)
        parser.add_argument("--output", help="Optional JSON copy of the staged candidate.")
        parser.add_argument("--single-page", action="store_true")
        parser.add_argument("--source-url", action="append", default=[], help="Explicit companion URL (repeatable).")
        parser.add_argument("--max-pages", type=int, default=3, help="Total pages to analyze, 1–5.")
        parser.add_argument("--force", action="store_true", help="Re-extract even if retrieved content is unchanged.")
    def handle(self, *args, **options):
        try:
            run = research_and_stage(options["url"], options["year"],
                follow_links=not options["single_page"], source_urls=options["source_url"],
                max_pages=options["max_pages"], force=options["force"])
        except (ValueError, requests.RequestException) as exc:
            message = str(exc) if isinstance(exc, ExtractionError) else "Website retrieval or extraction validation failed. No candidate was saved."
            raise CommandError(message) from None
        candidate = run.candidate
        if options["output"]:
            Path(options["output"]).write_text(json.dumps(candidate.raw_payload, indent=2), encoding="utf-8")
        if run.created:
            message = f"Candidate {candidate.pk} saved as needs_review. No trusted records changed."
        else:
            message = f"Content unchanged; reused candidate {candidate.pk} ({candidate.status}). No Gemini extraction calls made."
        self.stdout.write(self.style.SUCCESS(message))
