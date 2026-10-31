"""Integration acceptance tests for the complete M2 extraction/review/catalog workflow."""
import copy
import json
from unittest.mock import patch
from django.contrib.auth.models import User, Group
from django.core.management import call_command
from django.test import TestCase, Client
from django.urls import reverse
from io import StringIO
from .models import Conference, ConferenceEdition, Deadline, RegistrationPrice, ExtractionCandidate
from .tests import sample_payload
from .approval_service import approve_candidate
from .review_validation import ReviewValidationError, ReviewStateError

def pending_candidate(conflicts=False):
    payload = sample_payload()
    payload["registration_prices"][0].update(currency="USD",evidence="General early registration 450 USD",source_id="source_1")
    payload["deadlines"][0]["source_id"] = "source_1"
    payload["sources"] = [{"id":"source_1","source_url":"https://example.org/conf","title":"Official page","retrieved_at":"2026-10-30T12:00:00Z"}]
    payload["conflicts"] = [{"kind":"field","field":"location","alternatives":[{"value":"Atlanta, GA"},{"value":"Boston, MA"}]}] if conflicts else []
    return ExtractionCandidate.objects.create(requested_url=payload["requested_url"],raw_payload=payload)

def packet(candidate, **overrides):
    data = {"candidate_id":candidate.pk,"expected_status":"needs_review","requested_action":"approve","confirmed":True,
        "reviewed_values":{k:copy.deepcopy(candidate.raw_payload[k]) for k in ("fields","deadlines","registration_prices")},
        "reviewer_notes":"Checked the official source.","conflict_decisions":[],"replace_existing_rows":False}
    data.update(overrides)
    return data

class IntegratedFlowTests(TestCase):
    def setUp(self):
        call_command("setup_roles",stdout=StringIO())
        self.user=User.objects.create_user("m2-reviewer",password="test-review-password")
        self.user.groups.add(Group.objects.get(name="Reviewers"))
        self.client.force_login(self.user)
    def submit(self,candidate,data):
        return self.client.post(reverse("conferences:candidate_decision",args=[candidate.pk]),
                                data=json.dumps(data),content_type="application/json")
    @patch("conferences.ai_views.extract_and_stage")
    def test_url_to_candidate_review_correction_approval_and_catalog(self,extract):
        candidate=pending_candidate()
        extract.return_value=candidate
        response=self.client.post("/api/ai/extract/",data=json.dumps({"url":candidate.requested_url,"year":2027}),content_type="application/json")
        self.assertEqual(response.status_code,201)
        self.assertEqual(Conference.objects.count(),0)
        self.assertContains(self.client.get(reverse("conferences:review_workbench")),"Approve and save")
        self.assertEqual(self.client.get(f"/api/ai/candidates/{candidate.pk}/").status_code,200)
        review=packet(candidate)
        review["reviewed_values"]["fields"]["location"]["value"]="Marietta, GA"
        review["reviewed_values"]["deadlines"][0]["date"]="2027-01-20"
        review["reviewed_values"]["registration_prices"][0]["amount"]="475.00"
        original=copy.deepcopy(candidate.raw_payload)
        approved=self.submit(candidate,review)
        self.assertEqual(approved.status_code,200,approved.content)
        self.assertEqual(approved.json()["status"],"approved")
        candidate.refresh_from_db()
        self.assertEqual(candidate.raw_payload,original)
        self.assertEqual(candidate.reviewed_payload["fields"]["location"]["value"],"Marietta, GA")
        self.assertEqual(candidate.reviewed_by,"m2-reviewer")
        self.assertEqual(str(Deadline.objects.get(is_active=True).date),"2027-01-20")
        price=RegistrationPrice.objects.get(is_active=True)
        self.assertEqual(str(price.amount),"475.00")
        self.assertEqual(price.source_url,"https://example.org/conf")
        self.assertContains(self.client.get(approved.json()["conference_url"]),"Marietta, GA")
        self.assertContains(self.client.get(reverse("conferences:export_csv")),"Example Computing Conference")
    def test_rejection_writes_reason_without_catalog_records(self):
        candidate=pending_candidate()
        response=self.submit(candidate,packet(candidate,requested_action="reject",reviewer_notes="Conference edition is outdated."))
        self.assertEqual(response.status_code,200)
        candidate.refresh_from_db()
        self.assertEqual(candidate.status,"rejected")
        self.assertEqual(candidate.review_notes,"Conference edition is outdated.")
        self.assertFalse(Conference.objects.exists())
    def test_cannot_approve_or_reject_twice(self):
        candidate=pending_candidate()
        self.assertEqual(self.submit(candidate,packet(candidate)).status_code,200)
        self.assertEqual(self.submit(candidate,packet(candidate)).status_code,409)
        self.assertEqual(Conference.objects.count(),1)
        self.assertEqual(RegistrationPrice.objects.count(),1)
    def test_conflict_must_be_documented(self):
        candidate=pending_candidate(True)
        response=self.submit(candidate,packet(candidate))
        self.assertEqual(response.status_code,422)
        self.assertFalse(Conference.objects.exists())
    def test_conflict_resolution_is_audited(self):
        candidate=pending_candidate(True)
        data=packet(candidate,conflict_decisions=[{"decision_and_evidence":"Selected Boston based on the official venue page."}])
        data["reviewed_values"]["fields"]["location"]["value"]="Boston, MA"
        self.assertEqual(self.submit(candidate,data).status_code,200)
        candidate.refresh_from_db()
        self.assertEqual(ConferenceEdition.objects.get().location,"Boston, MA")
        self.assertEqual(len(candidate.reviewed_payload["review"]["conflict_decisions"]),1)
    def test_negative_reviewed_price_rejected(self):
        candidate=pending_candidate()
        data=packet(candidate)
        data["reviewed_values"]["registration_prices"][0]["amount"]="-1"
        self.assertEqual(self.submit(candidate,data).status_code,422)
        self.assertFalse(Conference.objects.exists())
    def test_invalid_deadline_is_rejected_before_writes(self):
        candidate=pending_candidate()
        data=packet(candidate)
        data["reviewed_values"]["deadlines"][0]["date"]="2027-02-30"
        self.assertEqual(self.submit(candidate,data).status_code,422)
        self.assertFalse(Conference.objects.exists())
    def test_date_range_and_edition_validation(self):
        candidate=pending_candidate()
        data=packet(candidate)
        data["reviewed_values"]["fields"]["end_date"]["value"]="2026-03-01"
        self.assertEqual(self.submit(candidate,data).status_code,422)
        self.assertFalse(Conference.objects.exists())
    def test_mismatched_candidate_id_rejected(self):
        candidate=pending_candidate()
        self.assertEqual(self.submit(candidate,packet(candidate,candidate_id=candidate.pk+1)).status_code,422)
    def test_final_source_confirmation_required(self):
        candidate=pending_candidate()
        self.assertEqual(self.submit(candidate,packet(candidate,confirmed=False)).status_code,422)
    def test_non_web_source_is_rejected(self):
        candidate=pending_candidate()
        data=packet(candidate)
        data["reviewed_values"]["deadlines"][0]["source_url"]="javascript:alert(1)"
        self.assertEqual(self.submit(candidate,data).status_code,422)
    def test_empty_snapshot_preserves_existing_rows_by_default(self):
        first=pending_candidate()
        self.assertEqual(self.submit(first,packet(first)).status_code,200)
        second=pending_candidate()
        data=packet(second)
        data["reviewed_values"]["deadlines"]=[]
        data["reviewed_values"]["registration_prices"]=[]
        self.assertEqual(self.submit(second,data).status_code,200)
        self.assertEqual(Deadline.objects.filter(is_active=True).count(),1)
        self.assertEqual(RegistrationPrice.objects.filter(is_active=True).count(),1)
    def test_explicit_replace_can_clear_existing_rows(self):
        first=pending_candidate()
        self.submit(first,packet(first))
        second=pending_candidate()
        data=packet(second,replace_existing_rows=True)
        data["reviewed_values"]["deadlines"]=[]
        data["reviewed_values"]["registration_prices"]=[]
        self.assertEqual(self.submit(second,data).status_code,200)
        self.assertFalse(Deadline.objects.filter(is_active=True).exists())
        self.assertFalse(RegistrationPrice.objects.filter(is_active=True).exists())
    def test_explicit_blank_clears_optional_location(self):
        candidate=pending_candidate()
        data=packet(candidate)
        data["reviewed_values"]["fields"]["location"]["value"]=None
        self.assertEqual(self.submit(candidate,data).status_code,200)
        edition=ConferenceEdition.objects.get()
        self.assertIsNone(edition.location)
        self.assertEqual(edition.information_status,"PARTIAL_INFORMATION")
    def test_viewer_cannot_submit_decisions(self):
        candidate=pending_candidate()
        self.client.force_login(User.objects.create_user("viewer"))
        self.assertEqual(self.submit(candidate,packet(candidate)).status_code,403)
        self.assertFalse(Conference.objects.exists())
    def test_csrf_required_and_successful_with_bootstrap(self):
        candidate=pending_candidate()
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        url=reverse("conferences:candidate_decision",args=[candidate.pk])
        body=json.dumps(packet(candidate))
        self.assertEqual(client.post(url,data=body,content_type="application/json").status_code,403)
        token=client.get("/api/ai/session/").json()["csrf_token"]
        self.assertEqual(client.post(url,data=body,content_type="application/json",HTTP_X_CSRFTOKEN=token).status_code,200)
    def test_original_form_cannot_bypass_conflict_resolution(self):
        candidate=pending_candidate(True)
        with self.assertRaises(ReviewValidationError):
            approve_candidate(candidate,reviewer="test")
        self.assertFalse(Conference.objects.exists())
    @patch("conferences.approval_service.RegistrationPrice.objects.create",side_effect=RuntimeError("simulated persistence error"))
    def test_database_error_rolls_back_all_catalog_writes(self,create):
        candidate=pending_candidate()
        with self.assertRaises(RuntimeError):
            approve_candidate(candidate,reviewer="test")
        candidate.refresh_from_db()
        self.assertEqual(candidate.status,"needs_review")
        self.assertFalse(Conference.objects.exists())
        self.assertFalse(Deadline.objects.exists())
    def test_previous_year_is_not_modified(self):
        previous=Conference.objects.create(name="Example Computing Conference")
        old=ConferenceEdition.objects.create(conference=previous,year=2026,location="Prior year venue")
        candidate=pending_candidate()
        self.assertEqual(self.submit(candidate,packet(candidate)).status_code,200)
        old.refresh_from_db()
        self.assertEqual(old.location,"Prior year venue")
        self.assertEqual(ConferenceEdition.objects.count(),2)


class DemoSetupTests(TestCase):
    def test_local_setup_is_repeatable_with_private_login_and_captured_candidate(self):
        import tempfile
        from pathlib import Path
        from django.test import override_settings
        original = pending_candidate().raw_payload
        original['extracted_at'] = '2026-10-30T12:00:00Z'
        ExtractionCandidate.objects.all().delete()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / 'ccse-conference-platform'
            base.mkdir()
            (root / 'candidate-live.json').write_text(json.dumps(original), encoding='utf-8')
            with override_settings(BASE_DIR=base, DEBUG=True):
                call_command('setup_m2_demo', stdout=StringIO())
                credentials = json.loads((root / '.m2-demo-login.json').read_text())
                user = User.objects.get(username=credentials['username'])
                self.assertTrue(user.check_password(credentials['password']))
                self.assertFalse(user.is_superuser)
                self.assertTrue(user.has_perm('conferences.change_extractioncandidate'))
                call_command('setup_m2_demo', stdout=StringIO())
                self.assertEqual(User.objects.filter(username='demo').count(), 1)
                self.assertEqual(ExtractionCandidate.objects.count(), 1)
                self.assertEqual(ExtractionCandidate.objects.get().raw_payload, original)
                self.assertEqual(json.loads((root / '.m2-demo-login.json').read_text()), credentials)
    def test_demo_setup_is_disabled_outside_development(self):
        from django.test import override_settings
        from django.core.management.base import CommandError
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            call_command('setup_m2_demo', stdout=StringIO())
    def test_browser_modules_have_a_javascript_content_type(self):
        import mimetypes
        self.assertEqual(mimetypes.guess_type('review-live.mjs')[0], 'application/javascript')
