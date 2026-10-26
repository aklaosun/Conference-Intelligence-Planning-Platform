"""A scheduler-friendly sequential worker; no web server or extra broker required."""
import json
from pathlib import Path
import requests
from django.core.management.base import BaseCommand, CommandError
from conferences.ai_service import ExtractionError, GeminiProvider, ProviderError
from conferences.research_service import research_and_stage, validate_options

class Command(BaseCommand):
    help = "Refresh a JSON manifest of conference URLs, skipping unchanged sources and reporting changes."
    def add_arguments(self, parser):
        parser.add_argument("manifest", help='JSON object: {"conferences": [{"url": "...", "year": 2027}]}')
        parser.add_argument("--output", required=True, help="Destination for a non-secret JSON run report.")
        parser.add_argument("--force", action="store_true")
    def handle(self, *args, **options):
        try:
            data = json.loads(Path(options["manifest"]).read_text(encoding="utf-8-sig"))
            entries = data["conferences"]
            if not isinstance(entries, list) or not 1 <= len(entries) <= 100:
                raise ValueError()
            for item in entries:
                if not isinstance(item, dict):
                    raise ValueError()
                validate_options(item.get("url"), item.get("year"), item.get("source_urls"), item.get("max_pages", 3))
                if type(item.get("follow_links", True)) is not bool:
                    raise ValueError()
        except (OSError, ValueError, KeyError, TypeError):
            raise CommandError("Manifest must contain 1–100 valid conference objects with url, optional year, follow_links, source_urls, and max_pages.") from None
        try:
            provider = GeminiProvider()
        except ProviderError as exc:
            raise CommandError(str(exc)) from None
        report = {"results": [], "stopped_on_provider_error": False}
        for item in entries:
            try:
                run = research_and_stage(item["url"], item.get("year"), provider=provider,
                    follow_links=item.get("follow_links", True), source_urls=item.get("source_urls"),
                    max_pages=item.get("max_pages", 3), force=options["force"])
                report["results"].append({"url":item["url"], "status":"created" if run.created else "unchanged",
                    "candidate_id":run.candidate.pk, "candidate_status":run.candidate.status,
                    "summary":run.candidate.raw_payload.get("summary", {}),
                    "changes":run.candidate.raw_payload.get("changes", {}) if run.created else {"previous_candidate_id":run.candidate.pk,"fields":[],"deadlines_changed":False,"registration_prices_changed":False}})
            except ProviderError as exc:
                report["results"].append({"url":item["url"], "status":"error", "error":str(exc)})
                report["stopped_on_provider_error"] = True
                break
            except (ValueError, requests.RequestException):
                report["results"].append({"url":item["url"], "status":"error",
                    "error":"Website retrieval or candidate validation failed; no candidate saved."})
        report["processed"] = len(report["results"])
        report["total"] = len(entries)
        Path(options["output"]).write_text(json.dumps(report,indent=2),encoding="utf-8")
        self.stdout.write(f"Processed {report['processed']}/{report['total']} conferences. Report: {options['output']}")
        if report["stopped_on_provider_error"] or any(r["status"] == "error" for r in report["results"]):
            raise CommandError("One or more refreshes failed; inspect the report. Trusted records were not changed.")
