import copy
import datetime as dt
from unittest.mock import patch
from django.test import SimpleTestCase,TestCase
from django.contrib.auth.models import User
from .cac_import import listed_dates,canonical_url,import_workbook
from .models import Conference,ConferenceEdition,RegistrationPrice,VerificationStatus


def sample():
    return {'name':'Sponsor Conference','url':'https://example.org/event','year':2026,
        'start':dt.date(2026,11,30),'end':dt.date(2026,12,4),'location':'Atlanta, GA',
        'format':'in_person','category':'Technology','source':{
            'id':'filehash:Sheet1:3','filename':'CAC.xlsx','sha256':'filehash','sheet':'Sheet1','row':3,
            'heading':'CAC 2026','listed_date':'30 NOV-4 DEC','year_basis':'workbook heading',
            'raw_values':{'NAME':'Sponsor Conference','COST':None,'NOTES':'Source note'},
            'focus_area':'Applied Computing','category':'Technology','notes':'Source note',
            'other_dates':'Another city event','warnings':['Year inferred from heading.']}}


class SponsorParsingTests(SimpleTestCase):
    def test_day_first_ranges_use_explicit_two_digit_year(self):
        start,end,year,basis,_=listed_dates('25-27 MAY 27',2026)
        self.assertEqual((start,end,year,basis),(dt.date(2027,5,25),dt.date(2027,5,27),2027,'date cell'))
    def test_yearless_dates_are_flagged_as_context_inference(self):
        start,end,year,basis,warnings=listed_dates('16-18 SEP',2026)
        self.assertEqual((start,end,year,basis),(dt.date(2026,9,16),dt.date(2026,9,18),2026,'workbook heading'))
        self.assertTrue(any('inferred' in w for w in warnings))
    def test_cross_month_range_is_preserved(self):
        start,end,*_=listed_dates('30 NOV-4 DEC',2026)
        self.assertEqual((start,end),(dt.date(2026,11,30),dt.date(2026,12,4)))
    def test_excel_date_does_not_fabricate_an_end_date(self):
        start,end,year,*_=listed_dates(dt.datetime(2027,3,8),2026)
        self.assertEqual(start,dt.date(2027,3,8))
        self.assertIsNone(end)
        self.assertEqual(year,2027)
    def test_prior_year_url_is_not_relabelled_as_2026(self):
        *_,year,basis,warnings=listed_dates(None,2026,'CASCON','https://conf.researchr.org/home/cascon-2025')
        self.assertEqual((year,basis),(2025,'website URL'))
        self.assertTrue(warnings)
    def test_atc_shorthand_is_retained_as_provisional_2025(self):
        self.assertEqual(listed_dates(None,2026,'USENIX','https://www.usenix.org/conference/atc25')[2],2025)
    def test_missing_date_remains_missing(self):
        start,end,year,*_=listed_dates(None,2026,'Example')
        self.assertIsNone(start)
        self.assertIsNone(end)
        self.assertEqual(year,2026)
    def test_invalid_date_is_flagged_without_guessing(self):
        start,end,_,_,warnings=listed_dates('31 FEB',2026)
        self.assertIsNone(start)
        self.assertIsNone(end)
        self.assertTrue(any('could not' in w for w in warnings))
    def test_tracking_removed_without_truncating_semantic_query(self):
        value=canonical_url('https://example.org/event?edition=2026&utm_source=google&gclid='+('x'*200))
        self.assertEqual(value,'https://example.org/event?edition=2026')
    def test_unsafe_or_overlong_links_are_not_silently_truncated(self):
        self.assertIsNone(canonical_url('javascript:alert(1)'))
        self.assertIsNone(canonical_url('https://example.org/'+('a'*210)))


class SponsorImportTests(TestCase):
    def run_import(self,records=None,**options):
        with patch('conferences.cac_import.workbook_records',return_value=records or [sample()]):
            return import_workbook('CAC.xlsx',**options)
    def test_dry_run_changes_nothing(self):
        report=self.run_import(dry_run=True)
        self.assertEqual(report['rows'],1)
        self.assertFalse(Conference.objects.exists())
        self.assertFalse(ConferenceEdition.objects.exists())
    def test_new_records_are_unverified_with_original_values_and_no_free_price(self):
        report=self.run_import()
        e=ConferenceEdition.objects.get()
        self.assertEqual(e.verification_status,VerificationStatus.NEEDS_REVIEW)
        self.assertTrue(e.conference.cac_relevant)
        self.assertEqual(e.field_sources['legacy_imports'][0]['raw_values']['NOTES'],'Source note')
        self.assertFalse(RegistrationPrice.objects.exists())
        self.assertEqual(report['editions_created'],1)
    def test_reimport_is_idempotent(self):
        self.run_import()
        report=self.run_import()
        self.assertEqual(report['already_imported'],1)
        self.assertEqual(ConferenceEdition.objects.count(),1)
        self.assertEqual(len(ConferenceEdition.objects.get().field_sources['legacy_imports']),1)
    def test_existing_verified_edition_is_preserved_and_website_alias_deduplicates(self):
        c=Conference.objects.create(name='Existing official conference name',website='https://example.org/event/')
        e=ConferenceEdition.objects.create(conference=c,year=2026,location='Reviewed venue',verification_status='VERIFIED')
        self.run_import()
        e.refresh_from_db()
        self.assertEqual(Conference.objects.count(),1)
        self.assertEqual(e.location,'Reviewed venue')
        self.assertEqual(e.verification_status,'VERIFIED')
        self.assertTrue(e.field_sources['legacy_imports'])
    def test_ambiguous_matching_rolls_back_whole_import(self):
        Conference.objects.create(name='One',website='https://example.org/event')
        Conference.objects.create(name='Two',website='https://example.org/event')
        with self.assertRaises(ValueError): self.run_import()
        self.assertFalse(ConferenceEdition.objects.exists())
    def test_notes_are_visible_in_detail_and_csv_and_html_is_escaped(self):
        record=sample()
        record['source']['notes']='<script>alert(1)</script> Source note'
        self.run_import([record])
        self.client.force_login(User.objects.create_user('spreadsheet-viewer'))
        e=ConferenceEdition.objects.get()
        page=self.client.get(f'/conferences/{e.conference_id}/')
        self.assertContains(page,'Imported spreadsheet data')
        self.assertContains(page,'&lt;script&gt;')
        self.assertNotContains(page,'<script>alert(1)</script>')
        csv=self.client.get('/conferences/export.csv').content.decode()
        self.assertIn('Spreadsheet notes',csv)
        self.assertIn('Source note',csv)
        self.assertIn('CAC.xlsx',csv)
