import datetime
import io
import json
import tempfile
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    Conference,
    ConferenceEdition,
    Deadline,
    ExtractionCandidate,
    InformationStatus,
    RegistrationPrice,
    VerificationStatus,
)
from .permissions import EDITORS, REVIEWERS


def sample_payload(**overrides):
    payload = {
        "schema_version": "1.0",
        "requested_url": "https://example.org/conf",
        "fields": {
            "conference_name": {"value": "Example Computing Conference", "evidence": "Page title", "confidence": 0.95},
            "organizer": {"value": "Example Society"},
            "year": {"value": 2027},
            "start_date": {"value": "2027-03-10"},
            "end_date": {"value": "2027-03-12"},
            "location": {"value": "Atlanta, GA"},
            "attendance_format": {"value": "in_person"},
            "themes": {"value": ["AI", "Security"]},
        },
        "deadlines": [{"type": "early_registration", "date": "2027-01-15", "evidence": "Early bird ends Jan 15"}],
        "registration_prices": [{"category": "General", "rate_type": "early_registration", "amount": "450.00"}],
        "warnings": ["Start time not listed"],
    }
    payload.update(overrides)
    return payload


def make_candidate(**overrides):
    payload = sample_payload(**overrides)
    return ExtractionCandidate.objects.create(requested_url=payload["requested_url"], raw_payload=payload)


class RoleSetupMixin:
    def setUp(self):
        call_command("setup_roles", stdout=io.StringIO())
        self.viewer = User.objects.create_user("viewer", password="pw-12345-x")
        self.editor = User.objects.create_user("editor", password="pw-12345-x")
        self.editor.groups.add(Group.objects.get(name=EDITORS))
        self.reviewer = User.objects.create_user("reviewer", password="pw-12345-x", first_name="Rae", last_name="View")
        self.reviewer.groups.add(Group.objects.get(name=REVIEWERS))


class LoginRequiredTests(TestCase):
    def test_pages_redirect_to_login(self):
        for name in ["conferences:dashboard", "conferences:conference_list", "conferences:candidate_list"]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("login"), response["Location"])

    def test_login_page_renders(self):
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)


class ReviewWorkflowTests(RoleSetupMixin, TestCase):
    def test_queue_lists_pending_only_by_default(self):
        pending = make_candidate()
        done = make_candidate()
        done.status = ExtractionCandidate.Status.APPROVED
        done.save()
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("conferences:candidate_list"))
        self.assertContains(response, reverse("conferences:candidate_detail", args=[pending.pk]))
        self.assertNotContains(response, reverse("conferences:candidate_detail", args=[done.pk]))

    def test_detail_shows_evidence_and_warnings(self):
        candidate = make_candidate()
        self.client.force_login(self.reviewer)
        response = self.client.get(reverse("conferences:candidate_detail", args=[candidate.pk]))
        self.assertContains(response, "Page title")
        self.assertContains(response, "Start time not listed")
        self.assertContains(response, "Approve")

    def test_viewer_cannot_approve(self):
        candidate = make_candidate()
        self.client.force_login(self.viewer)
        response = self.client.post(reverse("conferences:candidate_approve", args=[candidate.pk]), {})
        self.assertEqual(response.status_code, 403)
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, ExtractionCandidate.Status.NEEDS_REVIEW)

    def _form_data(self, candidate, **changes):
        data = {
            "conference_name": "Example Computing Conference",
            "organizer": "Example Society",
            "year": "2027",
            "start_date": "2027-03-10",
            "end_date": "2027-03-12",
            "start_time": "",
            "timezone": "",
            "location": "Atlanta, GA",
            "attendance_format": "in_person",
            "themes": "AI, Security",
            "target_audience": "",
        }
        data.update(changes)
        return data

    def test_approve_without_changes(self):
        candidate = make_candidate()
        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse("conferences:candidate_approve", args=[candidate.pk]), self._form_data(candidate)
        )
        self.assertRedirects(response, reverse("conferences:candidate_list"))
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, ExtractionCandidate.Status.APPROVED)
        self.assertEqual(candidate.reviewed_by, "Rae View")
        edition = ConferenceEdition.objects.get(conference__name="Example Computing Conference", year=2027)
        self.assertEqual(edition.location, "Atlanta, GA")
        self.assertEqual(edition.verification_status, VerificationStatus.VERIFIED)
        self.assertEqual(edition.deadlines.count(), 1)
        self.assertEqual(edition.registration_prices.count(), 1)

    def test_correct_then_approve_saves_corrected_value(self):
        candidate = make_candidate()
        self.client.force_login(self.reviewer)
        self.client.post(
            reverse("conferences:candidate_approve", args=[candidate.pk]),
            self._form_data(candidate, location="Marietta, GA"),
        )
        edition = ConferenceEdition.objects.get(year=2027)
        self.assertEqual(edition.location, "Marietta, GA")

    def test_correction_form_reports_only_changed_fields(self):
        from .forms import CandidateCorrectionForm
        candidate = make_candidate()
        form = CandidateCorrectionForm(self._form_data(candidate, location="Marietta, GA"), candidate=candidate)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.edited_fields(), {"location": "Marietta, GA"})

    def test_invalid_correction_is_rejected(self):
        candidate = make_candidate()
        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse("conferences:candidate_approve", args=[candidate.pk]),
            self._form_data(candidate, end_date="2027-03-01"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ConferenceEdition.objects.exists())

    def test_reject_requires_confirmation(self):
        candidate = make_candidate()
        self.client.force_login(self.reviewer)
        self.client.post(reverse("conferences:candidate_reject", args=[candidate.pk]), {})
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, ExtractionCandidate.Status.NEEDS_REVIEW)

        self.client.post(reverse("conferences:candidate_reject", args=[candidate.pk]), {"confirm": "on"})
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, ExtractionCandidate.Status.REJECTED)
        self.assertFalse(Conference.objects.exists())

    def test_cannot_review_twice(self):
        candidate = make_candidate()
        self.client.force_login(self.reviewer)
        self.client.post(reverse("conferences:candidate_reject", args=[candidate.pk]), {"confirm": "on"})
        self.client.post(
            reverse("conferences:candidate_approve", args=[candidate.pk]), self._form_data(candidate)
        )
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, ExtractionCandidate.Status.REJECTED)
        self.assertFalse(ConferenceEdition.objects.exists())


@override_settings(EXTRACTION_API_TOKEN="test-token")
class IngestionApiTests(TestCase):
    url = reverse("conferences:api_submit_candidate")

    def post(self, body, token="test-token"):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        return self.client.post(self.url, data=body, content_type="application/json", **headers)

    def test_creates_candidate(self):
        response = self.post(json.dumps(sample_payload()))
        self.assertEqual(response.status_code, 201)
        candidate = ExtractionCandidate.objects.get(pk=response.json()["id"])
        self.assertEqual(candidate.status, ExtractionCandidate.Status.NEEDS_REVIEW)
        self.assertEqual(candidate.raw_payload["warnings"], ["Start time not listed"])

    def test_rejects_bad_token(self):
        self.assertEqual(self.post(json.dumps(sample_payload()), token="nope").status_code, 401)
        self.assertEqual(self.post(json.dumps(sample_payload()), token=None).status_code, 401)
        self.assertFalse(ExtractionCandidate.objects.exists())

    def test_rejects_missing_fields(self):
        payload = sample_payload()
        del payload["fields"]["year"]
        response = self.post(json.dumps(payload))
        self.assertEqual(response.status_code, 400)
        self.assertIn("fields.year.value is required", response.json()["errors"])

    def test_rejects_non_json(self):
        self.assertEqual(self.post("not json").status_code, 400)

    @override_settings(EXTRACTION_API_TOKEN="")
    def test_disabled_without_token_setting(self):
        self.assertEqual(self.post(json.dumps(sample_payload()), token="").status_code, 401)


class ConferencePageTests(RoleSetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.ai = Conference.objects.create(name="AI Summit", organizer="ACM", cac_relevant=True, themes=["AI"])
        self.data = Conference.objects.create(name="Data Days", cdsa_relevant=True, themes=["Analytics"])
        self.both = Conference.objects.create(name="Joint Forum", cac_relevant=True, cdsa_relevant=True)
        future = datetime.date.today() + datetime.timedelta(days=90)
        self.ai_edition = ConferenceEdition.objects.create(
            conference=self.ai, year=future.year, start_date=future, location="Chicago, IL",
            attendance_format="hybrid",
        )
        ConferenceEdition.objects.create(conference=self.data, year=2020, location="Boston, MA",
                                         verification_status=VerificationStatus.VERIFIED)
        Deadline.objects.create(edition=self.ai_edition, type="registration",
                                date=datetime.date.today() + datetime.timedelta(days=20))

    def names(self, **params):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("conferences:conference_list"), params)
        return [c.name for c in response.context["page"]]

    def test_search_by_text_and_location(self):
        self.assertEqual(self.names(q="summit"), ["AI Summit"])
        self.assertEqual(self.names(q="boston"), ["Data Days"])
        self.assertEqual(self.names(q="acm"), ["AI Summit"])

    def test_filter_by_center(self):
        self.assertEqual(self.names(center="cac"), ["AI Summit", "Joint Forum"])
        self.assertEqual(self.names(center="cdsa"), ["Data Days", "Joint Forum"])
        self.assertEqual(self.names(center="both"), ["Joint Forum"])

    def test_filter_by_edition_fields(self):
        self.assertEqual(self.names(year=2020), ["Data Days"])
        self.assertEqual(self.names(verification_status="VERIFIED"), ["Data Days"])
        self.assertEqual(self.names(attendance_format="hybrid"), ["AI Summit"])
        self.assertEqual(self.names(upcoming_only="on"), ["AI Summit"])

    def test_dashboard_shows_upcoming_deadline(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("conferences:dashboard"))
        self.assertEqual(response.context["conference_count"], 3)
        self.assertEqual(len(response.context["upcoming_deadlines"]), 1)

    def test_inactive_deadlines_are_hidden(self):
        Deadline.objects.create(edition=self.ai_edition, type="old_cfp", is_active=False,
                                date=datetime.date.today() + datetime.timedelta(days=10))
        self.client.force_login(self.viewer)
        self.assertEqual(len(self.client.get(reverse("conferences:dashboard")).context["upcoming_deadlines"]), 1)
        response = self.client.get(reverse("conferences:conference_detail", args=[self.ai.pk]))
        self.assertNotContains(response, "old_cfp")

    def test_reapproval_replaces_stale_deadlines(self):
        first = make_candidate()
        self.client.force_login(self.reviewer)
        from .approval_service import approve_candidate
        approve_candidate(first)
        second = make_candidate(deadlines=[{"type": "early_registration", "date": "2027-01-30"}])
        approve_candidate(second)
        edition = ConferenceEdition.objects.get(conference__name="Example Computing Conference")
        self.assertEqual(list(edition.deadlines.filter(is_active=True).values_list("date", flat=True)),
                         [datetime.date(2027, 1, 30)])
        self.assertEqual(edition.deadlines.filter(is_active=False).count(), 1)

    def test_detail_page(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("conferences:conference_detail", args=[self.ai.pk]))
        self.assertContains(response, "Chicago, IL")
        self.assertContains(response, "registration")
        self.assertNotContains(response, "Add edition")

    def test_viewer_cannot_edit(self):
        self.client.force_login(self.viewer)
        response = self.client.post(reverse("conferences:conference_edit", args=[self.ai.pk]), {"name": "X"})
        self.assertEqual(response.status_code, 403)

    def test_editor_can_edit_conference(self):
        self.client.force_login(self.editor)
        response = self.client.post(reverse("conferences:conference_edit", args=[self.ai.pk]), {
            "name": "AI Summit", "organizer": "IEEE", "website": "", "themes": "AI, ML",
            "target_audience": "", "cac_relevant": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.ai.refresh_from_db()
        self.assertEqual(self.ai.organizer, "IEEE")
        self.assertEqual(self.ai.themes, ["AI", "ML"])

    def _edition_post(self, **extra):
        data = {
            "year": "2028", "start_date": "2028-05-01", "end_date": "2028-05-03", "start_time": "",
            "timezone": "", "location": "Denver, CO", "attendance_format": "in_person",
            "information_status": InformationStatus.COMPLETE, "verification_status": VerificationStatus.VERIFIED,
            "source_url": "",
            "deadlines-TOTAL_FORMS": "1", "deadlines-INITIAL_FORMS": "0",
            "deadlines-0-type": "registration", "deadlines-0-date": "2028-04-01", "deadlines-0-is_active": "on",
            "prices-TOTAL_FORMS": "1", "prices-INITIAL_FORMS": "0",
            "prices-0-category": "Student", "prices-0-rate_type": "regular",
            "prices-0-amount": "199.00", "prices-0-currency": "USD", "prices-0-is_active": "on",
        }
        data.update(extra)
        return data

    def test_editor_can_add_edition_with_deadline_and_price(self):
        self.client.force_login(self.editor)
        response = self.client.post(reverse("conferences:edition_create", args=[self.ai.pk]), self._edition_post())
        self.assertEqual(response.status_code, 302)
        edition = ConferenceEdition.objects.get(conference=self.ai, year=2028)
        self.assertEqual(edition.deadlines.get().type, "registration")
        self.assertEqual(str(edition.registration_prices.get().amount), "199.00")

    def test_edition_end_before_start_is_rejected(self):
        self.client.force_login(self.editor)
        response = self.client.post(
            reverse("conferences:edition_create", args=[self.ai.pk]), self._edition_post(end_date="2028-04-01")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ConferenceEdition.objects.filter(year=2028).exists())

    def test_csv_export_respects_filters(self):
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("conferences:export_csv"), {"center": "cdsa"})
        body = response.content.decode()
        self.assertIn("Data Days", body)
        self.assertNotIn("AI Summit", body)


class LegacyImportTests(TestCase):
    def run_import(self, text, *args):
        folder = tempfile.mkdtemp()
        path = Path(folder) / "legacy.csv"
        path.write_text(text, encoding="utf-8")
        out = io.StringIO()
        call_command("import_legacy_excel", str(path), *args, stdout=out)
        return out.getvalue()

    CSV = (
        "Conference Name,Dates,Location,Website,Center,Registration Cost,Early Bird Deadline,Format,Notes\n"
        "Grace Hopper Celebration,\"Oct 6-9, 2026\",\"Orlando, FL\",ghc.anitab.org,CAC,\"$1,250\",07/15/2026,In Person,go\n"
        "grace hopper celebration,\"Oct 1-4, 2025\",\"Philadelphia, PA\",,CDSA,,,Hybrid,\n"
        "Data Science Week,\"March 3 - March 5, 2027\",,,both CAC/CDSA,TBD,,Virtual,\n"
        "Mystery Conf,,,,,,,,\n"
    )

    def test_imports_and_merges_duplicates(self):
        out = self.run_import(self.CSV)
        self.assertEqual(Conference.objects.count(), 2)
        ghc = Conference.objects.get(name="Grace Hopper Celebration")
        self.assertTrue(ghc.cac_relevant and ghc.cdsa_relevant)
        self.assertEqual(ghc.website, "https://ghc.anitab.org")
        self.assertEqual(sorted(ghc.editions.values_list("year", flat=True)), [2025, 2026])

        e2026 = ghc.editions.get(year=2026)
        self.assertEqual(e2026.start_date, datetime.date(2026, 10, 6))
        self.assertEqual(e2026.end_date, datetime.date(2026, 10, 9))
        self.assertEqual(e2026.information_status, InformationStatus.NEEDS_VERIFICATION)
        self.assertEqual(e2026.verification_status, VerificationStatus.NEEDS_REVIEW)
        self.assertEqual(e2026.deadlines.get().date, datetime.date(2026, 7, 15))
        self.assertEqual(str(e2026.registration_prices.get().amount), "1250.00")

        dsw = Conference.objects.get(name="Data Science Week").editions.get()
        self.assertEqual(dsw.start_date, datetime.date(2027, 3, 3))
        self.assertEqual(dsw.attendance_format, "virtual")
        self.assertEqual(dsw.information_status, InformationStatus.PARTIAL_INFORMATION)

        self.assertIn("Mystery Conf", out)
        self.assertIn("no matching field): Notes", out)
        self.assertNotIn("couldn't read dates ''", out)
        self.assertIn("couldn't read cost 'TBD'", out)

    def test_dry_run_saves_nothing(self):
        out = self.run_import(self.CSV, "--dry-run")
        self.assertIn("Dry run", out)
        self.assertFalse(Conference.objects.exists())

    def test_rerun_does_not_duplicate(self):
        self.run_import(self.CSV)
        out = self.run_import(self.CSV)
        self.assertEqual(ConferenceEdition.objects.count(), 3)
        self.assertEqual(Deadline.objects.count(), 1)
        self.assertEqual(RegistrationPrice.objects.count(), 1)
        self.assertIn("already exists", out)

    def test_default_year(self):
        self.run_import(self.CSV, "--default-year", "2026")
        self.assertTrue(ConferenceEdition.objects.filter(conference__name="Mystery Conf", year=2026).exists())

    def test_xlsx(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Conference", "Start Date", "End Date", "City"])
        ws.append(["Excel Conf", datetime.datetime(2026, 11, 2), datetime.datetime(2026, 11, 4), "Austin, TX"])
        path = Path(tempfile.mkdtemp()) / "legacy.xlsx"
        wb.save(path)
        call_command("import_legacy_excel", str(path), stdout=io.StringIO())
        edition = ConferenceEdition.objects.get(conference__name="Excel Conf")
        self.assertEqual(edition.year, 2026)
        self.assertEqual(edition.end_date, datetime.date(2026, 11, 4))
        self.assertEqual(edition.location, "Austin, TX")
