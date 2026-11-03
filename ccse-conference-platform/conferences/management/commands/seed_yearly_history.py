import datetime
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from conferences.models import (
    AttendanceFormat,
    BudgetLine,
    Conference,
    ConferenceEdition,
    ConferencePlan,
    Deadline,
    InformationStatus,
    OutcomeReport,
    PlanningStage,
    RegistrationPrice,
    VerificationStatus,
)

NAME = "Southeast Applied Computing Summit"

EDITIONS = [
    {
        "year": 2025,
        "start_date": datetime.date(2025, 4, 14),
        "end_date": datetime.date(2025, 4, 16),
        "location": "Atlanta, GA",
        "deadlines": [("early_registration", datetime.date(2025, 2, 15)), ("registration", datetime.date(2025, 3, 31))],
        "prices": [("General", "450.00"), ("Student", "200.00")],
        "stage": "attended",
        "budget": [("registration", "Three general registrations", "1350.00", "1350.00"),
                   ("travel", "Mileage", "300.00", "264.50")],
        "outcome": ("Sent three faculty. Met two regional employers about student projects.", 3, 9, 1),
    },
    {
        "year": 2026,
        "start_date": datetime.date(2026, 4, 20),
        "end_date": datetime.date(2026, 4, 22),
        "location": "Charlotte, NC",
        "deadlines": [("early_registration", datetime.date(2026, 2, 20)), ("registration", datetime.date(2026, 4, 1))],
        "prices": [("General", "495.00"), ("Student", "225.00")],
        "stage": "attended",
        "budget": [("registration", "Four general registrations", "1980.00", "1980.00"),
                   ("lodging", "Two nights, two rooms", "880.00", None)],
        "outcome": ("Sent four attendees. Presented a poster and followed up with one partner from 2025.", 4, 14, 2),
    },
]


class Command(BaseCommand):
    help = "Create a demo conference with two yearly editions to show that each year keeps its own records"

    def handle(self, *args, **options):
        call_command("setup_platform", verbosity=0, stdout=self.stdout)
        with transaction.atomic():
            conference, _ = Conference.objects.get_or_create(
                name=NAME,
                defaults={"organizer": "Demo data (not a real event)", "website": "https://example.org/seacs/"},
            )
            conference.add_centers("CAC")
            conference.set_themes(["Applied Computing", "Industry Partnerships"])
            for spec in EDITIONS:
                self.make_edition(conference, spec)
        self.stdout.write(self.style.SUCCESS(f"{NAME}: editions {', '.join(str(s['year']) for s in EDITIONS)} ready"))

    def make_edition(self, conference, spec):
        edition, _ = ConferenceEdition.objects.update_or_create(
            conference=conference,
            year=spec["year"],
            defaults={
                "start_date": spec["start_date"],
                "end_date": spec["end_date"],
                "location": spec["location"],
                "attendance_format": AttendanceFormat.IN_PERSON,
                "information_status": InformationStatus.COMPLETE,
                "verification_status": VerificationStatus.VERIFIED,
                "source_url": f"https://example.org/seacs/{spec['year']}/",
            },
        )
        for kind, date in spec["deadlines"]:
            Deadline.objects.update_or_create(edition=edition, type=kind, defaults={"date": date, "is_active": True})
        for category, amount in spec["prices"]:
            RegistrationPrice.objects.update_or_create(
                edition=edition, category=category, rate_type="regular",
                defaults={"amount": Decimal(amount), "currency": "USD", "is_active": True},
            )
        plan, _ = ConferencePlan.objects.get_or_create(
            edition=edition, defaults={"stage": PlanningStage.objects.get(code=spec["stage"])}
        )
        for category, description, estimated, actual in spec["budget"]:
            BudgetLine.objects.update_or_create(
                plan=plan, category=category, description=description,
                defaults={"currency": "USD", "estimated": Decimal(estimated),
                          "actual": Decimal(actual) if actual else None},
            )
        summary, attendees, contacts, partnerships = spec["outcome"]
        OutcomeReport.objects.update_or_create(
            edition=edition,
            defaults={"summary": summary, "attendees": attendees, "contacts": contacts, "partnerships": partnerships},
        )
