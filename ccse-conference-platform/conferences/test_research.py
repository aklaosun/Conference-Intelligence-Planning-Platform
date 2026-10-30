import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from io import StringIO
from unittest.mock import patch
import requests
from django.test import SimpleTestCase, TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from django.contrib.auth.models import User
from .test_ai import page, response, FixtureProvider, EXAMPLES
from .ai_service import CandidateValidationError, ProviderError, create_candidate_payload
from .research_service import (
    ResearchRun, collect_pages, select_companion_links, merge_payloads, attach_source,
    research_and_stage, validate_options,
)
from .models import ExtractionCandidate, Conference, ConferenceEdition

def companion():
    p = page()
    p["requested_url"] = p["source_url"] = "https://example.org/conference/register"
    p["text"] += "\nRegistration page for the same edition."
    return p

def pages_with_links():
    p = page()
    p["links"] = [
        {"url":"https://example.org/2026/register", "text":"Old registration"},
        {"url":"https://outside.example/register", "text":"Register"},
        {"url":"https://example.org/conference/cfp", "text":"Call for papers"},
        {"url":"https://example.org/conference/register", "text":"Registration"},
        {"url":"https://example.org/conference/register#pricing", "text":"Fees"},
        {"url":"https://example.org/conference/program", "text":"Program"},
    ]
    return p

def pair_payloads(second=None):
    primary = attach_source(create_candidate_payload(page(),FixtureProvider()),page(),"source_1")
    child = attach_source(create_candidate_payload(companion(),FixtureProvider(second)),companion(),"source_2")
    return primary, child

class LinkSelectionTests(SimpleTestCase):
    def test_priority_and_edition_filter(self):
        urls=select_companion_links(pages_with_links(),2027,2)
        self.assertEqual(urls,["https://example.org/conference/register","https://example.org/conference/cfp"])
    def test_zero_limit(self):
        self.assertEqual(select_companion_links(pages_with_links(),2027,0),[])
    def test_invalid_options(self):
        for count in (0,6,True):
            with self.assertRaises(CandidateValidationError):
                validate_options("https://example.org",2027,[],count)
    def test_explicit_sources_not_silently_truncated(self):
        with self.assertRaises(CandidateValidationError):
            validate_options("https://example.org",2027,["https://example.org/one","https://example.org/two"],2)
    @patch("conferences.research_service.fetch_conference_page")
    def test_optional_companion_failure_warns(self,fetch):
        fetch.side_effect=[pages_with_links(),requests.Timeout()]
        pages,warnings=collect_pages("https://example.org/conference",expected_year=2027,max_pages=2)
        self.assertEqual(len(pages),1)
        self.assertTrue(any("could not be retrieved" in w for w in warnings))
    @patch("conferences.research_service.fetch_conference_page")
    def test_auto_offhost_redirect_excluded(self,fetch):
        other=companion()
        other["source_url"]="https://outside.example/register"
        fetch.side_effect=[pages_with_links(),other]
        pages,warnings=collect_pages("https://example.org/conference",expected_year=2027,max_pages=2)
        self.assertEqual(len(pages),1)
        self.assertTrue(any("another hostname" in w for w in warnings))
    @patch("conferences.research_service.fetch_conference_page")
    def test_explicit_offhost_source_allowed(self,fetch):
        other=companion()
        other["source_url"]="https://outside.example/register"
        fetch.side_effect=[page(),other]
        pages,warnings=collect_pages("https://example.org/conference",expected_year=2027,
            follow_links=False,source_urls=["https://outside.example/register"],max_pages=2)
        self.assertEqual(len(pages),2)
    @patch("conferences.research_service.fetch_conference_page")
    def test_root_failure_is_fatal(self,fetch):
        fetch.side_effect=requests.Timeout()
        with self.assertRaises(requests.Timeout):
            collect_pages("https://example.org/conference")

class MergeTests(SimpleTestCase):
    def test_provenance_and_duplicate_rows(self):
        result=merge_payloads(pair_payloads())
        self.assertEqual(len(result["sources"]),2)
        self.assertEqual(len(result["deadlines"]),1)
        self.assertEqual(result["deadlines"][0]["additional_evidence"][0]["source_id"],"source_2")
        self.assertEqual(len(result["registration_prices"]),1)
        self.assertEqual(result["fields"]["location"]["corroborating_sources"],["source_1","source_2"])
    def test_conflicting_location_is_blank_with_alternatives(self):
        raw=response()
        raw["fields"]["location"]={"value":"Boston","evidence":"Example Computing Conference 2027"}
        result=merge_payloads(pair_payloads(raw))
        self.assertIsNone(result["fields"]["location"]["value"])
        self.assertEqual(len(result["fields"]["location"]["alternatives"]),2)
        self.assertTrue(any(c["field"]=="location" for c in result["conflicts"] if c["kind"]=="field"))
    def test_conflicting_deadlines_are_preserved_and_flagged(self):
        raw=response()
        raw["deadlines"][0]["date"]="2027-01-16"
        result=merge_payloads(pair_payloads(raw))
        self.assertEqual(len(result["deadlines"]),0)
        self.assertTrue(any(c["kind"]=="deadlines" for c in result["conflicts"]))
    def test_conflicting_prices_are_flagged(self):
        one,two=pair_payloads()
        two["registration_prices"][0]["amount"]="150.00"
        result=merge_payloads([one,two])
        self.assertTrue(any(c["kind"]=="registration_prices" for c in result["conflicts"]))
    def test_missing_root_field_filled_from_companion(self):
        one,two=pair_payloads()
        one["fields"]["location"].update(value=None,evidence=None,source_id=None)
        merged=merge_payloads([one,two])
        self.assertEqual(merged["fields"]["location"]["source_id"],"source_2")
    def test_sources_retain_analyzed_text_and_hash(self):
        merged=merge_payloads(pair_payloads())
        self.assertIn("Example Computing",merged["sources"][1]["analyzed_text"])
        self.assertEqual(len(merged["sources"][1]["content_sha256"]),64)

class ResearchIntegrationTests(TestCase):
    @patch("conferences.research_service.fetch_conference_page")
    def test_repeat_skips_model_calls_and_candidate_creation(self,fetch):
        fetch.return_value=page()
        provider=FixtureProvider()
        with patch.object(provider,"extract",wraps=provider.extract) as extract:
            one=research_and_stage(page()["requested_url"],2027,provider=provider,follow_links=False)
            two=research_and_stage(page()["requested_url"],2027,provider=provider,follow_links=False)
        self.assertTrue(one.created)
        self.assertFalse(two.created)
        self.assertEqual(one.candidate.pk,two.candidate.pk)
        self.assertEqual(extract.call_count,1)
        self.assertEqual(ExtractionCandidate.objects.count(),1)
        self.assertEqual(Conference.objects.count(),0)
        self.assertEqual(ConferenceEdition.objects.count(),0)
    @patch("conferences.research_service.fetch_conference_page")
    def test_force_bypasses_unchanged_check(self,fetch):
        fetch.return_value=page()
        for force in [False,True]:
            research_and_stage(page()["requested_url"],2027,provider=FixtureProvider(),follow_links=False,force=force)
        self.assertEqual(ExtractionCandidate.objects.count(),2)
    @patch("conferences.research_service.fetch_conference_page")
    def test_changed_fact_has_previous_value(self,fetch):
        fetch.return_value=page()
        first=research_and_stage(page()["requested_url"],2027,provider=FixtureProvider(),follow_links=False)
        changed=page()
        changed["text"]+="\nBoston"
        raw=response()
        raw["fields"]["location"]={"value":"Boston","evidence":"Boston"}
        fetch.return_value=changed
        second=research_and_stage(page()["requested_url"],2027,provider=FixtureProvider(raw),follow_links=False)
        change=next(c for c in second.candidate.raw_payload["changes"]["fields"] if c["field"]=="location")
        self.assertEqual(change,{"field":"location","before":"Atlanta, Georgia","after":"Boston"})
        self.assertEqual(second.candidate.raw_payload["changes"]["previous_candidate_id"],first.candidate.pk)
    @patch("conferences.research_service.fetch_conference_page")
    def test_prompt_revision_invalidates_cached_result(self,fetch):
        fetch.return_value=page()
        research_and_stage(page()["requested_url"],2027,provider=FixtureProvider(),follow_links=False)
        with patch("conferences.research_service.PROMPT_VERSION","next-prompt"):
            run=research_and_stage(page()["requested_url"],2027,provider=FixtureProvider(),follow_links=False)
        self.assertTrue(run.created)
    @patch("conferences.research_service.fetch_conference_page")
    def test_wrong_edition_root_never_saved(self,fetch):
        fetch.return_value=page()
        with self.assertRaises(CandidateValidationError):
            research_and_stage(page()["requested_url"],2028,provider=FixtureProvider(),follow_links=False)
        self.assertEqual(ExtractionCandidate.objects.count(),0)
    @patch("conferences.research_service.fetch_conference_page")
    def test_companion_wrong_edition_is_excluded(self,fetch):
        fetch.side_effect=[pages_with_links(),companion()]
        raw=response()
        raw["fields"]["year"]["value"]=2026
        raw["fields"]["start_date"]["value"]="2026-06-10"
        raw["fields"]["end_date"]["value"]="2026-06-12"
        provider=FixtureProvider()
        provider.extract=lambda p,year=None: response() if p["source_url"]==page()["source_url"] else raw
        run=research_and_stage(page()["requested_url"],2027,provider=provider,max_pages=2)
        self.assertEqual(len(run.candidate.raw_payload["sources"]),1)
        self.assertTrue(any("excluded" in w for w in run.candidate.raw_payload["warnings"]))
    @patch("conferences.research_service.fetch_conference_page")
    def test_provider_error_on_child_never_saves_partial_candidate(self,fetch):
        fetch.side_effect=[pages_with_links(),companion()]
        provider=FixtureProvider()
        with patch.object(provider,"extract",side_effect=[response(),ProviderError("quota")]):
            with self.assertRaises(ProviderError):
                research_and_stage(page()["requested_url"],2027,provider=provider,max_pages=2)
        self.assertEqual(ExtractionCandidate.objects.count(),0)
    @patch("conferences.research_service.fetch_conference_page")
    def test_missing_child_year_is_associated_only_with_current_source_context(self,fetch):
        fetch.side_effect=[pages_with_links(),companion()]
        raw=response()
        raw["fields"]["year"]={"value":None,"evidence":None}
        provider=FixtureProvider()
        with patch.object(provider,"extract",side_effect=[response(),raw]):
            run=research_and_stage(page()["requested_url"],2027,provider=provider,max_pages=2)
        self.assertEqual(len(run.candidate.raw_payload["sources"]),2)
        self.assertEqual(run.candidate.raw_payload["fields"]["year"]["value"],2027)
    @patch("conferences.research_service.fetch_conference_page")
    def test_command_exports_candidate(self,fetch):
        fetch.return_value=page()
        with TemporaryDirectory(dir=EXAMPLES.parent) as folder, patch("conferences.research_service.GeminiProvider",return_value=FixtureProvider()):
            target=Path(folder)/"candidate.json"
            call_command("extract_conference",page()["requested_url"],year=2027,single_page=True,output=str(target),stdout=StringIO())
            self.assertEqual(json.loads(target.read_text())["schema_version"],"1.1")

class CandidateListTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("ai-reviewer"))
        for status in ["needs_review","approved","needs_review"]:
            ExtractionCandidate.objects.create(requested_url=page()["requested_url"],raw_payload={},status=status)
    def test_pending_default_pagination(self):
        data=self.client.get("/api/ai/candidates/?page_size=1").json()
        self.assertEqual(data["count"],2)
        self.assertEqual(len(data["results"]),1)
        self.assertNotIn("payload",data["results"][0])
    def test_status_all(self):
        self.assertEqual(self.client.get("/api/ai/candidates/?status=all").json()["count"],3)
    def test_invalid_pagination_rejected(self):
        self.assertEqual(self.client.get("/api/ai/candidates/?page_size=0").status_code,400)
    def test_anonymous_blocked(self):
        self.client.logout()
        self.assertEqual(self.client.get("/api/ai/candidates/").status_code,302)
    def test_bad_extraction_options_rejected(self):
        self.assertEqual(self.client.post("/api/ai/extract/",data=json.dumps({"url":"https://example.org","follow_links":"yes"}),content_type="application/json").status_code,400)
    @patch("conferences.ai_views.extract_and_stage",side_effect=CandidateValidationError("wrong edition"))
    def test_edition_error_returns_422(self,extract):
        self.assertEqual(self.client.post("/api/ai/extract/",data=json.dumps({"url":"https://example.org"}),content_type="application/json").status_code,422)

class RefreshCommandTests(TestCase):
    def test_invalid_manifest_does_not_start_provider(self):
        with TemporaryDirectory(dir=EXAMPLES.parent) as folder:
            manifest=Path(folder)/"input.json"
            manifest.write_text('{"conferences":[]}')
            with self.assertRaises(CommandError), patch("conferences.management.commands.refresh_conferences.GeminiProvider") as provider:
                call_command("refresh_conferences",str(manifest),output=str(Path(folder)/"report.json"),stdout=StringIO())
            provider.assert_not_called()
    @patch("conferences.management.commands.refresh_conferences.GeminiProvider",return_value=FixtureProvider())
    @patch("conferences.research_service.fetch_conference_page",return_value=page())
    def test_batch_report_and_repeat_skip(self,fetch,provider):
        with TemporaryDirectory(dir=EXAMPLES.parent) as folder:
            manifest=Path(folder)/"input.json"
            report=Path(folder)/"report.json"
            manifest.write_text(json.dumps({"conferences":[{"url":page()["requested_url"],"year":2027,"follow_links":False}]}))
            call_command("refresh_conferences",str(manifest),output=str(report),stdout=StringIO())
            self.assertEqual(json.loads(report.read_text())["results"][0]["status"],"created")
            call_command("refresh_conferences",str(manifest),output=str(report),stdout=StringIO())
            self.assertEqual(json.loads(report.read_text())["results"][0]["status"],"unchanged")
    @patch("conferences.management.commands.refresh_conferences.GeminiProvider",return_value=FixtureProvider())
    @patch("conferences.management.commands.refresh_conferences.research_and_stage",side_effect=ProviderError("quota"))
    def test_provider_failure_stops_batch(self,research,provider):
        with TemporaryDirectory(dir=EXAMPLES.parent) as folder:
            manifest=Path(folder)/"input.json"
            report=Path(folder)/"report.json"
            manifest.write_text(json.dumps({"conferences":[{"url":"https://example.org/one"},{"url":"https://example.org/two"}]}))
            with self.assertRaises(CommandError):
                call_command("refresh_conferences",str(manifest),output=str(report),stdout=StringIO())
            data=json.loads(report.read_text())
            self.assertTrue(data["stopped_on_provider_error"])
            self.assertEqual(research.call_count,1)
            self.assertEqual(data["processed"],1)



class LiveResearchRegressionTests(SimpleTestCase):
    def test_track_specific_deadline_keys(self):
        from .ai_service import canonical_deadline_type
        self.assertEqual(canonical_deadline_type("Submission Deadline","Posters Submission Deadline 13 March"),"poster_submission")
        self.assertEqual(canonical_deadline_type("Submission Deadline","Special Session Abstracts Submission Deadline 15 February"),"special_session_abstract_submission")
    def test_embedded_css_crossed_out(self):
        from .extraction_service import parse_conference_html
        p=parse_conference_html('<style>.old { text-decoration: line-through; }</style><body><span class="old">old date</span>new date</body>',"https://example.org","https://example.org")
        self.assertIn("[CROSSED OUT: old date]",p["text"])
    def test_surcharge_not_full_registration(self):
        from .ai_service import registration_price_problem
        problem=registration_price_problem({"category":"ACM Member","rate_type":"Late","amount":"150.00","currency":"EUR","evidence":"Early Registration Fee + 150 Euros"})
        self.assertIn("surcharge",problem)
    def test_calculated_unpublished_total_rejected(self):
        from .ai_service import registration_price_problem
        problem=registration_price_problem({"category":"ACM Member","rate_type":"Late","amount":"800.00","currency":"EUR","evidence":"Early Registration Fee + 150 Euros"})
        self.assertIn("amount does not appear",problem)
    def test_euro_symbol_is_unambiguous(self):
        from .ai_service import registration_price_problem
        self.assertIsNone(registration_price_problem({"category":"Student","rate_type":"early","amount":"450.00","currency":"EUR","evidence":"Student early registration €450"}))


class FinalIntegrationTests(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_superuser("integration-reviewer"))
    def test_session_sets_csrf_and_permissions(self):
        response=self.client.get("/api/ai/session/")
        self.assertEqual(response.status_code,200)
        self.assertIn("csrftoken",response.cookies)
        self.assertTrue(response.json()["permissions"]["extract"])
        self.assertTrue(response.json()["csrf_token"])
    def test_read_only_user_session_permission_flags(self):
        user=User.objects.create_user("ordinary-user")
        self.client.force_login(user)
        permissions=self.client.get("/api/ai/session/").json()["permissions"]
        self.assertFalse(permissions["extract"])
        self.assertFalse(permissions["view_candidates"])
    def test_ai_role_does_not_grant_approval_or_delete_rights(self):
        from django.contrib.auth.models import Group
        call_command("configure_ai_role",stdout=StringIO())
        group=Group.objects.get(name="AI Researchers")
        self.assertEqual(set(group.permissions.values_list("codename",flat=True)),
                         {"add_extractioncandidate","view_extractioncandidate"})

class TimezoneMergeRegressionTests(SimpleTestCase):
    def test_aoe_quote_is_preserved_without_numeric_conversion(self):
        raw=response()
        raw["deadlines"][0].update(timezone="UTC+12",evidence="January 15, 2027 (AoE)")
        source=page()
        source["text"]+="\nJanuary 15, 2027 (AoE)"
        payload=create_candidate_payload(source,FixtureProvider(raw))
        self.assertEqual(payload["deadlines"][0]["timezone"],"AoE")
    def test_absent_timezone_does_not_create_false_conflict(self):
        one,two=pair_payloads()
        one["deadlines"][0]["timezone"]=None
        two["deadlines"][0]["timezone"]="AoE"
        merged=merge_payloads([one,two])
        self.assertEqual(len(merged["deadlines"]),1)
        self.assertEqual(merged["deadlines"][0]["timezone"],"AoE")
        self.assertFalse(any(c["kind"]=="deadlines" for c in merged["conflicts"]))


class CsrfIntegrationTests(TestCase):
    @patch("conferences.ai_views.extract_and_stage")
    def test_session_bootstrap_allows_csrf_protected_post(self, extract):
        from django.test import Client
        from unittest.mock import Mock
        user=User.objects.create_superuser("csrf-integration")
        client=Client(enforce_csrf_checks=True)
        client.force_login(user)
        token=client.get("/api/ai/session/").json()["csrf_token"]
        extract.return_value=Mock(pk=1,status="needs_review",raw_payload={},reviewed_payload=None,conference_id=None,_ai_created=True)
        result=client.post("/api/ai/extract/",data=json.dumps({"url":"https://example.org"}),
                           content_type="application/json",HTTP_X_CSRFTOKEN=token)
        self.assertEqual(result.status_code,201)
    def test_role_setup_is_idempotent(self):
        from django.contrib.auth.models import Group
        for _ in range(2):
            call_command("configure_ai_role",stdout=StringIO())
        self.assertEqual(Group.objects.filter(name="AI Researchers").count(),1)
