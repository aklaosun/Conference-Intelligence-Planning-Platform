import datetime
import io
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from .approval_service import approve_candidate
from .models import (
    Center,
    Conference,
    ConferenceEdition,
    Deadline,
    ExtractionCandidate,
    OutcomeReport,
    RegistrationPrice,
    Theme,
)

BEFORE = [("conferences", "0004_planning_and_access")]
AFTER = [("conferences", "0007_remove_center_flags_and_theme_json")]
FIXTURE = Path(__file__).resolve().parents[2] / "data" / "demo-catalog.json"


class NormalizationMigrationTests(TransactionTestCase):
    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        self.migrate(executor_leaf())

    def test_existing_flags_and_themes_move_into_tables_and_back(self):
        old = self.migrate(BEFORE)
        OldConference = old.get_model("conferences", "Conference")
        OldConference.objects.create(name="Both Centers", cac_relevant=True, cdsa_relevant=True,
                                     themes=["AI", " ai ", "Data  Science"])
        OldConference.objects.create(name="CAC Only", cac_relevant=True, themes=["Data Science"])
        OldConference.objects.create(name="Unassigned", themes=[])

        new = self.migrate(AFTER)
        NewConference = new.get_model("conferences", "Conference")
        Center = new.get_model("conferences", "Center")
        Theme = new.get_model("conferences", "Theme")
        self.assertEqual(sorted(Center.objects.values_list("code", flat=True)), ["CAC", "CCSE", "CDSA"])
        self.assertEqual(sorted(Theme.objects.values_list("name", flat=True)), ["AI", "Data Science"])
        both = NewConference.objects.get(name="Both Centers")
        self.assertEqual(sorted(both.centers.values_list("code", flat=True)), ["CAC", "CDSA"])
        self.assertEqual(sorted(both.themes.values_list("name", flat=True)), ["AI", "Data Science"])
        cac = NewConference.objects.get(name="CAC Only")
        self.assertEqual(list(cac.centers.values_list("code", flat=True)), ["CAC"])
        self.assertEqual(cac.themes.get().pk, Theme.objects.get(key="data science").pk)
        self.assertFalse(NewConference.objects.get(name="Unassigned").centers.exists())

        old = self.migrate(BEFORE)
        OldConference = old.get_model("conferences", "Conference")
        both = OldConference.objects.get(name="Both Centers")
        self.assertTrue(both.cac_relevant and both.cdsa_relevant)
        self.assertEqual(both.themes, ["AI", "Data Science"])
        cac = OldConference.objects.get(name="CAC Only")
        self.assertEqual((cac.cac_relevant, cac.cdsa_relevant, cac.themes), (True, False, ["Data Science"]))


def executor_leaf():
    executor = MigrationExecutor(connection)
    return executor.loader.graph.leaf_nodes()


class CenterThemeModelTests(TestCase):
    def test_centers_are_seeded(self):
        self.assertEqual(list(Center.objects.values_list("code", flat=True)), ["CAC", "CCSE", "CDSA"])

    def test_themes_are_shared_and_case_insensitive(self):
        first = Conference.objects.create(name="First")
        second = Conference.objects.create(name="Second")
        first.set_themes(["Cybersecurity", "AI"])
        second.set_themes(["cybersecurity ", "Cloud"])
        self.assertEqual(Theme.objects.count(), 3)
        self.assertEqual(Theme.objects.get(key="cybersecurity").conferences.count(), 2)
        second.set_themes(["Cloud"])
        self.assertEqual(second.theme_names, ["Cloud"])
        self.assertEqual(Theme.objects.get(key="cybersecurity").conferences.count(), 1)

    def test_center_helpers(self):
        conference = Conference.objects.create(name="Shared")
        conference.add_centers("CDSA", "CAC", "NOPE")
        self.assertEqual(conference.center_codes, ["CAC", "CDSA"])
        conference.set_centers(["CCSE"])
        self.assertEqual(conference.center_codes, ["CCSE"])
        self.assertTrue(conference.has_center("CCSE"))

    def test_approval_writes_themes_to_relationship_table(self):
        payload = {
            "requested_url": "https://example.org/conf",
            "fields": {
                "conference_name": {"value": "Theme Conference"},
                "year": {"value": 2027},
                "themes": {"value": ["Machine Learning", "Security"]},
            },
            "deadlines": [],
            "registration_prices": [],
        }
        candidate = ExtractionCandidate.objects.create(requested_url=payload["requested_url"], raw_payload=payload)
        approve_candidate(candidate, reviewer="tester")
        conference = Conference.objects.get(name="Theme Conference")
        self.assertEqual(conference.theme_names, ["Machine Learning", "Security"])

    def test_platform_api_keeps_center_and_theme_lists(self):
        user = User.objects.create_superuser("owner", password="Owner-password-123")
        conference = Conference.objects.create(name="API Conference")
        conference.add_centers("CAC", "CDSA")
        conference.set_themes(["AI"])
        ConferenceEdition.objects.create(conference=conference, year=2027)
        self.client.force_login(user)
        data = self.client.get(f"/api/platform/catalog/{conference.pk}/").json()
        self.assertEqual(data["centers"], ["CAC", "CDSA"])
        self.assertEqual(data["themes"], ["AI"])
        catalog = self.client.get("/api/platform/catalog/", {"center": "both"}).json()
        self.assertEqual([row["name"] for row in catalog["results"]], ["API Conference"])

    def test_desktop_fixture_loads(self):
        call_command("loaddata", str(FIXTURE), verbosity=0)
        self.assertEqual(Conference.objects.count(), 35)
        self.assertEqual(Conference.objects.filter(centers__code="CAC").count(), 35)
        self.assertEqual(Theme.objects.count(), 9)
        self.assertEqual(Conference.objects.get(name="QUANTUM TECH").theme_names, ["Technology"])


class YearlyHistoryTests(TestCase):
    def setUp(self):
        call_command("seed_yearly_history", stdout=io.StringIO())
        self.conference = Conference.objects.get(name="Southeast Applied Computing Summit")

    def test_each_year_keeps_its_own_records(self):
        e2025, e2026 = (self.conference.editions.get(year=y) for y in (2025, 2026))
        self.assertEqual(e2025.start_date, datetime.date(2025, 4, 14))
        self.assertEqual(e2026.start_date, datetime.date(2026, 4, 20))
        self.assertEqual(e2025.location, "Atlanta, GA")
        self.assertEqual(e2026.location, "Charlotte, NC")
        self.assertEqual(e2025.registration_prices.get(category="General").amount, Decimal("450.00"))
        self.assertEqual(e2026.registration_prices.get(category="General").amount, Decimal("495.00"))
        self.assertEqual(e2025.deadlines.get(type="early_registration").date, datetime.date(2025, 2, 15))
        self.assertEqual(e2026.deadlines.get(type="early_registration").date, datetime.date(2026, 2, 20))
        self.assertEqual(e2025.outcome.attendees, 3)
        self.assertEqual(e2026.outcome.attendees, 4)
        self.assertEqual(e2025.plan.budget_lines.get(category="registration").actual, Decimal("1350.00"))

    def test_approving_new_year_does_not_touch_previous_year(self):
        e2025 = self.conference.editions.get(year=2025)
        before = (e2025.start_date, e2025.location, list(e2025.deadlines.values_list("type", "date", "is_active")),
                  list(e2025.registration_prices.values_list("category", "amount", "is_active")), e2025.outcome.summary)
        payload = {
            "requested_url": "https://example.org/seacs/2027",
            "fields": {
                "conference_name": {"value": self.conference.name},
                "year": {"value": 2027},
                "start_date": {"value": "2027-04-12"},
                "end_date": {"value": "2027-04-14"},
                "location": {"value": "Nashville, TN"},
            },
            "deadlines": [{"type": "early_registration", "date": "2027-02-18"}],
            "registration_prices": [{"category": "General", "rate_type": "early", "amount": "525.00", "currency": "USD"}],
        }
        candidate = ExtractionCandidate.objects.create(requested_url=payload["requested_url"], raw_payload=payload)
        approve_candidate(candidate, reviewer="tester")
        self.assertEqual(self.conference.editions.count(), 3)
        e2025.refresh_from_db()
        after = (e2025.start_date, e2025.location, list(e2025.deadlines.values_list("type", "date", "is_active")),
                 list(e2025.registration_prices.values_list("category", "amount", "is_active")), e2025.outcome.summary)
        self.assertEqual(before, after)
        e2027 = self.conference.editions.get(year=2027)
        self.assertEqual(e2027.registration_prices.get().amount, Decimal("525.00"))
        self.assertFalse(OutcomeReport.objects.filter(edition=e2027).exists())

    def test_seed_is_repeatable(self):
        call_command("seed_yearly_history", stdout=io.StringIO())
        self.assertEqual(Conference.objects.filter(name=self.conference.name).count(), 1)
        self.assertEqual(self.conference.editions.count(), 2)
        self.assertEqual(Deadline.objects.filter(edition__conference=self.conference).count(), 4)
        self.assertEqual(RegistrationPrice.objects.filter(edition__conference=self.conference).count(), 4)

    def test_history_shows_on_conference_page(self):
        user = User.objects.create_superuser("owner", password="Owner-password-123")
        self.client.force_login(user)
        response = self.client.get(reverse("conferences:conference_detail", args=[self.conference.pk]))
        self.assertContains(response, "Atlanta, GA")
        self.assertContains(response, "Charlotte, NC")
        self.assertContains(response, "450.00")
        self.assertContains(response, "495.00")
