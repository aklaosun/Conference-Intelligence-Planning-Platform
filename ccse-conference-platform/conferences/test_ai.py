import copy
import json
from pathlib import Path
from unittest.mock import Mock, patch
import requests
from django.test import TestCase, SimpleTestCase, Client
from django.contrib.auth.models import User
from pydantic import ValidationError
from .ai_service import GeminiProvider, ExtractionError, create_candidate_payload, extract_and_stage
from .extraction_service import parse_conference_html, validate_public_url, fetch_conference_page
from .models import ExtractionCandidate, Conference, ConferenceEdition
from .approval_service import approve_candidate

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
def page():
    return json.loads((EXAMPLES / "synthetic-page.json").read_text())
def response():
    return json.loads((EXAMPLES / "synthetic-response.json").read_text())
class FixtureProvider:
    model = "synthetic-fixture"
    def __init__(self, payload=None):
        self.payload = payload or response()
    def extract(self, page, expected_year=None):
        return copy.deepcopy(self.payload)

class ValidationTests(SimpleTestCase):
    def test_valid_candidate(self):
        p = create_candidate_payload(page(), FixtureProvider(), 2027)
        self.assertEqual(p["status"], "needs_review")
        self.assertEqual(p["registration_prices"][0]["amount"], "100.00")
        self.assertEqual(p["deadlines"][0]["source_url"], page()["source_url"])
    def test_missing_evidence_removed(self):
        raw = response()
        raw["fields"]["organizer"] = {"value": "Fabricated organizer", "evidence": "absent quote"}
        p = create_candidate_payload(page(), FixtureProvider(raw))
        self.assertIsNone(p["fields"]["organizer"]["value"])
    def test_crossed_out_deadline_removed(self):
        raw = response()
        raw["deadlines"][0].update(date="2027-01-01", evidence="January 1, 2027")
        self.assertEqual(create_candidate_payload(page(), FixtureProvider(raw))["deadlines"], [])
    def test_wrong_edition_rejected(self):
        with self.assertRaises(ExtractionError):
            create_candidate_payload(page(), FixtureProvider(), 2028)
    def test_invalid_date_rejected(self):
        raw = response()
        raw["fields"]["start_date"]["value"] = "2027-02-30"
        with self.assertRaises(ValidationError):
            create_candidate_payload(page(), FixtureProvider(raw))
    def test_reversed_dates_rejected(self):
        raw = response()
        raw["fields"]["end_date"]["value"] = "2027-06-01"
        with self.assertRaises(ValidationError):
            create_candidate_payload(page(), FixtureProvider(raw))
    def test_negative_price_rejected(self):
        raw = response()
        raw["registration_prices"][0]["amount"] = "-1"
        with self.assertRaises(ValidationError):
            create_candidate_payload(page(), FixtureProvider(raw))
    def test_ambiguous_currency_rejected(self):
        raw = response()
        raw["registration_prices"][0]["currency"] = "$"
        with self.assertRaises(ValidationError):
            create_candidate_payload(page(), FixtureProvider(raw))
    def test_truncation_warning(self):
        p = page()
        p["text"] += "x" * 60001
        self.assertTrue(any("60000" in w for w in create_candidate_payload(p, FixtureProvider())["warnings"]))
    def test_html_crossed_out_preserved(self):
        p = parse_conference_html('<html><title>Test</title><body><script>secret</script><s>old</s><span style="text-decoration:line-through">older</span>current</body></html>', "https://example.org", "https://example.org")
        self.assertIn("[CROSSED OUT: old]", p["text"])
        self.assertIn("[CROSSED OUT: older]", p["text"])
        self.assertNotIn("secret", p["text"])
    @patch("conferences.extraction_service.socket.getaddrinfo", return_value=[(2,1,6,"",("127.0.0.1",80))])
    def test_private_addresses_rejected(self, dns):
        with self.assertRaises(ValueError):
            validate_public_url("http://localhost/")
    def test_non_http_rejected(self):
        with self.assertRaises(ValueError):
            validate_public_url("file:///etc/passwd")
    @patch("conferences.extraction_service.validate_public_url")
    @patch("conferences.extraction_service.requests.Session")
    def test_redirect_target_revalidated(self, session, validate):
        validate.side_effect = [None, ValueError("private")]
        result = Mock(status_code=302, headers={"Location":"http://127.0.0.1/"})
        session.return_value.__enter__.return_value.get.return_value.__enter__.return_value = result
        with self.assertRaises(ValueError):
            fetch_conference_page("https://example.org")
        self.assertEqual(validate.call_count, 2)

@patch("conferences.ai_service.read_local_env", new=lambda: {})
class ProviderTests(SimpleTestCase):
    @patch.dict("os.environ", {}, clear=True)
    def test_key_missing(self):
        with self.assertRaises(ExtractionError):
            GeminiProvider()
    @patch("conferences.ai_service.requests.post")
    def test_rest_response_parsed(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":json.dumps(response())}]}}]}
        self.assertIn("fields", GeminiProvider("private-test-key-for-unit-tests-only").extract(page()))
        self.assertNotIn("store", post.call_args.kwargs["json"])
        self.assertIn(":generateContent", post.call_args.args[0])
        self.assertIn("responseJsonSchema", post.call_args.kwargs["json"]["generationConfig"])
        self.assertNotIn("private-test-key-for-unit-tests-only", post.call_args.args[0])
    @patch("conferences.ai_service.requests.post")
    def test_quota_error(self, post):
        post.return_value = Mock(status_code=429)
        with self.assertRaisesMessage(ExtractionError, "quota"):
            GeminiProvider("private-test-key-for-unit-tests-only").extract(page())
        self.assertEqual(post.call_count, 1)
    @patch("conferences.ai_service.requests.post", side_effect=requests.Timeout("sensitive transport data"))
    def test_timeout_sanitized(self, post):
        with self.assertRaisesMessage(ExtractionError, "timed out"):
            GeminiProvider("private-test-key-for-unit-tests-only").extract(page())
    @patch("conferences.ai_service.requests.post")
    def test_incomplete_output_rejected(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {"status":"failed"}
        with self.assertRaises(ExtractionError):
            GeminiProvider("private-test-key-for-unit-tests-only").extract(page())

class IntegrationTests(TestCase):
    @patch("conferences.extraction_service.fetch_conference_page", side_effect=lambda url: page())
    def test_staging_does_not_create_trusted_records(self, fetch):
        c = extract_and_stage("https://example.org/conference", 2027, FixtureProvider())
        self.assertEqual(c.status, "needs_review")
        self.assertEqual(Conference.objects.count(), 0)
        self.assertEqual(ConferenceEdition.objects.count(), 0)
    @patch("conferences.extraction_service.fetch_conference_page", side_effect=lambda url: page())
    def test_existing_approval_can_consume_payload(self, fetch):
        c = extract_and_stage("https://example.org/conference", 2027, FixtureProvider())
        edition = approve_candidate(c, reviewer="fixture-reviewer")
        self.assertEqual(edition.year, 2027)
        self.assertEqual(edition.deadlines.count(), 1)
        self.assertEqual(edition.registration_prices.count(), 1)
    @patch("conferences.extraction_service.fetch_conference_page", side_effect=lambda url: page())
    def test_invalid_extraction_never_saved(self, fetch):
        with self.assertRaises(ExtractionError):
            extract_and_stage("https://example.org/conference", 2028, FixtureProvider())
        self.assertEqual(ExtractionCandidate.objects.count(), 0)
    def test_anonymous_redirected(self):
        self.assertEqual(self.client.post("/api/ai/extract/", data="{}", content_type="application/json").status_code, 302)
    def test_unprivileged_forbidden(self):
        user = User.objects.create_user("viewer")
        self.client.force_login(user)
        self.assertEqual(self.client.post("/api/ai/extract/", data="{}", content_type="application/json").status_code, 403)
    def test_csrf_required(self):
        user = User.objects.create_superuser("admin", password="test-only-password")
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        self.assertEqual(client.post("/api/ai/extract/", data="{}", content_type="application/json").status_code, 403)
    @patch("conferences.ai_views.extract_and_stage")
    def test_authenticated_api_returns_candidate(self, extract):
        user = User.objects.create_superuser("admin")
        self.client.force_login(user)
        payload = create_candidate_payload(page(), FixtureProvider())
        c = ExtractionCandidate.objects.create(requested_url=page()["requested_url"],raw_payload=payload)
        extract.return_value = c
        result = self.client.post("/api/ai/extract/", data=json.dumps({"url":page()["requested_url"],"year":2027}), content_type="application/json")
        self.assertEqual(result.status_code,201)
        self.assertEqual(result.json()["status"],"needs_review")
        self.assertEqual(self.client.get(f"/api/ai/candidates/{c.pk}/").json()["payload"],payload)
    def test_bad_json_rejected(self):
        self.client.force_login(User.objects.create_superuser("admin"))
        self.assertEqual(self.client.post("/api/ai/extract/", data="[]", content_type="application/json").status_code,400)



@patch("conferences.ai_service.read_local_env", new=lambda: {})
class GeminiRequestRegressionTests(SimpleTestCase):
    def test_schema_avoids_complex_decimal_branches_and_refs(self):
        from .ai_service import gemini_response_schema
        schema = gemini_response_schema()
        text = json.dumps(schema)
        for unsupported in ('"$ref"', '"$defs"', '"pattern"', '"anyOf"'):
            self.assertNotIn(unsupported, text)
        amount = schema["properties"]["registration_prices"]["items"]["properties"]["amount"]
        self.assertEqual(amount["type"], "string")
        year = schema["properties"]["fields"]["properties"]["year"]["properties"]["value"]
        self.assertEqual(year["type"], ["integer", "null"])
    @patch("conferences.ai_service.requests.post")
    def test_http400_shows_message_without_key(self, post):
        key = "private-test-key-for-unit-tests-only"
        post.return_value = Mock(status_code=400)
        post.return_value.json.return_value = {"error":{"message":f"Unsupported schema. key={key}"}}
        with self.assertRaises(ExtractionError) as caught:
            GeminiProvider(key).extract(page())
        self.assertIn("Unsupported schema", str(caught.exception))
        self.assertNotIn(key, str(caught.exception))
        self.assertIn("[REDACTED]", str(caught.exception))
    def test_other_key_in_error_is_redacted(self):
        from .ai_service import safe_provider_error
        result = Mock()
        result.json.return_value = {"error":{"message":"Invalid key=another-secret, unsupported request"}}
        self.assertNotIn("another-secret", safe_provider_error(result, "test-key"))
    def test_non_json_error_is_safe(self):
        from .ai_service import safe_provider_error
        result = Mock()
        result.json.side_effect = ValueError()
        self.assertIn("No readable provider error", safe_provider_error(result, "test-key"))



@patch("conferences.ai_service.read_local_env", new=lambda: {})
class GeminiConnectionTests(SimpleTestCase):
    def test_incomplete_key_rejected_before_network(self):
        with self.assertRaisesMessage(ExtractionError, "incomplete"):
            GeminiProvider("*")
    @patch("conferences.ai_service.requests.get")
    def test_key_and_model_preflight_success(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {"models":[{"name":"models/test-flash","supportedGenerationMethods":["generateContent"]}]}
        self.assertEqual(GeminiProvider("fake-key-for-unit-tests-only", model="test-flash").check_access(), "test-flash")
        self.assertNotIn("fake-key", get.call_args.args[0])
    @patch("conferences.ai_service.requests.get")
    def test_unavailable_model_returns_choices(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {"models":[{"name":"models/available-flash","supportedGenerationMethods":["generateContent"]}]}
        with self.assertRaisesMessage(ExtractionError, "available-flash"):
            GeminiProvider("fake-key-for-unit-tests-only", model="unavailable").check_access()
    def test_top_level_error_is_redacted(self):
        from .ai_service import safe_provider_error
        result=Mock()
        result.json.return_value={"message":"Invalid request with key=secret-value"}
        message=safe_provider_error(result,"fake-key-for-unit-tests-only")
        self.assertIn("Invalid request",message)
        self.assertNotIn("secret-value",message)
    def test_array_error_is_supported(self):
        from .ai_service import safe_provider_error
        result=Mock()
        result.json.return_value=[{"error":{"message":"Request field not recognized"}}]
        self.assertIn("not recognized",safe_provider_error(result,"fake-key-for-unit-tests-only"))



class DotEnvTests(SimpleTestCase):
    @patch("pathlib.Path.read_text", return_value="# local config\nGEMINI_API_KEY=fake-key-for-unit-tests-only\nGEMINI_MODEL=test-flash\nIGNORED=value\n")
    def test_read_allowed_settings(self, read):
        from .ai_service import read_local_env
        self.assertEqual(read_local_env("unused-test-file"), {"GEMINI_API_KEY":"fake-key-for-unit-tests-only", "GEMINI_MODEL":"test-flash"})
    @patch("pathlib.Path.read_text", return_value='GEMINI_API_KEY="fake-key-for-unit-tests-only"\n')
    def test_quotes_are_removed(self, read):
        from .ai_service import read_local_env
        self.assertEqual(read_local_env("unused-test-file")["GEMINI_API_KEY"],"fake-key-for-unit-tests-only")
    @patch("pathlib.Path.read_text", return_value='GEMINI_API_KEY="unclosed\n')
    def test_bad_quotes_do_not_echo_value(self, read):
        from .ai_service import read_local_env
        with self.assertRaises(ExtractionError) as caught:
            read_local_env("unused-test-file")
        self.assertNotIn("unclosed",str(caught.exception))
    @patch("conferences.ai_service.read_local_env", return_value={"GEMINI_API_KEY":"fake-dotenv-key-for-unit-tests", "GEMINI_MODEL":"test-flash"})
    @patch.dict("os.environ", {"GEMINI_API_KEY":"stale-process-key-for-unit-tests"}, clear=True)
    def test_project_key_is_used_over_stale_environment(self, config):
        p=GeminiProvider()
        self.assertEqual(p.api_key,"fake-dotenv-key-for-unit-tests")
        self.assertEqual(p.model,"test-flash")
    @patch("conferences.ai_service.read_local_env", return_value={"GEMINI_API_KEY":"fake-dotenv-key-for-unit-tests"})
    def test_explicit_key_has_priority(self, config):
        self.assertEqual(GeminiProvider("explicit-fake-key-for-unit-tests").api_key,"explicit-fake-key-for-unit-tests")



class RegistrationPriceSafetyTests(SimpleTestCase):
    def test_article_processing_charges_excluded(self):
        raw=response()
        raw["registration_prices"][0].update(category="ACM/SIG members",rate_type="APC",amount="250.00",currency="USD",evidence="250.00 USD APC for ACM/SIG members")
        source=page()
        source["text"]+="\n250.00 USD APC for ACM/SIG members"
        payload=create_candidate_payload(source,FixtureProvider(raw))
        self.assertEqual(payload["registration_prices"],[])
        self.assertTrue(any("publication charges" in w for w in payload["warnings"]))
    def test_ambiguous_dollar_symbol_does_not_establish_usd(self):
        raw=response()
        raw["registration_prices"][0]["evidence"]="Student early registration: $100.00"
        source=page()
        source["text"]+="\nStudent early registration: $100.00"
        payload=create_candidate_payload(source,FixtureProvider(raw))
        self.assertEqual(payload["registration_prices"],[])
        self.assertTrue(any("currency" in w for w in payload["warnings"]))
    def test_explicit_currency_registration_preserved(self):
        payload=create_candidate_payload(page(),FixtureProvider())
        self.assertEqual(len(payload["registration_prices"]),1)
    def test_empty_prices_have_warning(self):
        raw=response()
        raw["registration_prices"]=[]
        payload=create_candidate_payload(page(),FixtureProvider(raw))
        self.assertTrue(any("no supported attendance registration prices" in w for w in payload["warnings"]))



class EventTimezoneSafetyTests(SimpleTestCase):
    def test_deadline_aoe_not_assigned_to_event(self):
        raw=response()
        raw["fields"]["timezone"]={"value":"AoE","evidence":"All deadlines are AoE."}
        source=page()
        source["text"]+="\nAll deadlines are AoE."
        payload=create_candidate_payload(source,FixtureProvider(raw))
        self.assertIsNone(payload["fields"]["timezone"]["value"])
        self.assertTrue(any("deadline convention" in w for w in payload["warnings"]))
