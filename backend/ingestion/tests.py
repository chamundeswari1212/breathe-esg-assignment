"""
Focused tests for the ESG ingestion platform.

Covers:
- SAP normalization (fuel recognition, unit handling, date parsing, non-fuel flagging)
- Utility normalization (billing period validation, usage thresholds)
- Travel normalization (flight distance estimation, hotel nights, missing data)
- Review workflow (approve, reject, lock, locked-cannot-edit)
- Audit log creation
- Upload endpoint integration
"""
import json
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import Tenant, DataSource, ImportBatch, RawRecord, EmissionRecord, AuditLog
from .normalizers.sap import SAPNormalizer
from .normalizers.utility import UtilityNormalizer
from .normalizers.travel import TravelNormalizer


class SAPNormalizerTests(TestCase):
    """Tests for SAP fuel & procurement normalization."""

    def setUp(self):
        self.normalizer = SAPNormalizer()

    def test_diesel_recognized_as_scope1(self):
        row = {'BELNR': '5000001', 'BUDAT': '15.03.2026', 'Werk': 'PL01',
               'MATNR': 'MAT-1001', 'MAKTX': 'Diesel Fuel', 'Menge': '1200',
               'MEINS': 'L', 'LIFNR': 'V-2001'}
        result = self.normalizer.normalize_row(row)
        self.assertIsNone(result['error'])
        self.assertEqual(result['fields']['scope'], 'Scope 1')
        self.assertEqual(result['fields']['activity_type'], 'Diesel Combustion')
        self.assertAlmostEqual(result['fields']['estimated_emissions_kgco2e'], 1200 * 2.68, places=1)

    def test_german_date_format(self):
        row = {'BUDAT': '15.03.2026', 'Werk': 'PL01', 'MAKTX': 'Diesel Fuel',
               'Menge': '100', 'MEINS': 'L'}
        result = self.normalizer.normalize_row(row)
        self.assertIsNone(result['error'])
        self.assertEqual(str(result['fields']['period_start']), '2026-03-15')

    def test_sap_internal_date_format(self):
        row = {'BUDAT': '20260320', 'Werk': 'PL02', 'MAKTX': 'Diesel Fuel',
               'Menge': '100', 'MEINS': 'L'}
        result = self.normalizer.normalize_row(row)
        self.assertIsNone(result['error'])
        self.assertEqual(str(result['fields']['period_start']), '2026-03-20')

    def test_invalid_date_flagged(self):
        row = {'BUDAT': 'invalid-date', 'Werk': 'PL01', 'MAKTX': 'Diesel Fuel',
               'Menge': '800', 'MEINS': 'L'}
        result = self.normalizer.normalize_row(row)
        self.assertIn('date_parse_failure', result['flags'])
        self.assertEqual(result['confidence'], 'LOW')

    def test_unit_normalization(self):
        row = {'BUDAT': '2026-03-01', 'Werk': 'PL01', 'MAKTX': 'Benzin (Petrol)',
               'Menge': '350', 'MEINS': 'liter'}
        result = self.normalizer.normalize_row(row)
        self.assertEqual(result['fields']['unit_normalized'], 'L')

    def test_zero_quantity_flagged(self):
        row = {'BUDAT': '2026-03-01', 'Werk': 'PL01', 'MAKTX': 'Diesel Fuel',
               'Menge': '0', 'MEINS': 'L'}
        result = self.normalizer.normalize_row(row)
        self.assertIn('zero_quantity', result['flags'])

    def test_negative_quantity_flagged(self):
        row = {'BUDAT': '2026-03-01', 'Werk': 'PL01', 'MAKTX': 'Diesel Fuel',
               'Menge': '-50', 'MEINS': 'L'}
        result = self.normalizer.normalize_row(row)
        self.assertIn('negative_quantity', result['flags'])

    def test_missing_plant_flagged(self):
        row = {'BUDAT': '2026-03-01', 'Werk': '', 'MAKTX': 'Diesel Fuel',
               'Menge': '500', 'MEINS': 'L'}
        result = self.normalizer.normalize_row(row)
        self.assertIn('missing_plant', result['flags'])

    def test_non_fuel_procurement_flagged(self):
        row = {'BUDAT': '2026-03-01', 'Werk': 'PL01', 'MAKTX': 'Office Supplies',
               'Menge': '25', 'MEINS': 'KG'}
        result = self.normalizer.normalize_row(row)
        self.assertIn('procurement_not_fuel', result['flags'])
        self.assertEqual(result['fields']['scope'], 'Scope 3')
        self.assertEqual(result['confidence'], 'LOW')

    def test_unknown_material_flagged(self):
        row = {'BUDAT': '2026-03-01', 'Werk': 'PL01', 'MAKTX': 'Unknown Material XYZ',
               'Menge': '300', 'MEINS': 'KG'}
        result = self.normalizer.normalize_row(row)
        self.assertIn('unknown_material', result['flags'])

    def test_unparseable_quantity_fails(self):
        row = {'BUDAT': '2026-03-01', 'Werk': 'PL01', 'MAKTX': 'Diesel Fuel',
               'Menge': 'abc', 'MEINS': 'L'}
        result = self.normalizer.normalize_row(row)
        self.assertIsNotNone(result['error'])


class UtilityNormalizerTests(TestCase):
    """Tests for utility electricity normalization."""

    def setUp(self):
        self.normalizer = UtilityNormalizer()

    def test_standard_electricity_scope2(self):
        row = {'meter_id': 'MTR-001', 'account_number': 'ACCT-100',
               'billing_start': '2026-03-01', 'billing_end': '2026-03-31',
               'usage_kwh': '24500', 'demand_kw': '85',
               'tariff': 'Commercial-TOU', 'facility': 'Main Office'}
        result = self.normalizer.normalize_row(row)
        self.assertIsNone(result['error'])
        self.assertEqual(result['fields']['scope'], 'Scope 2')
        self.assertAlmostEqual(result['fields']['estimated_emissions_kgco2e'], 24500 * 0.417, places=1)

    def test_billing_end_before_start_flagged(self):
        row = {'meter_id': 'MTR-005', 'account_number': 'ACCT-104',
               'billing_start': '2026-04-30', 'billing_end': '2026-04-01',
               'usage_kwh': '22000', 'demand_kw': '75',
               'tariff': 'Commercial-TOU', 'facility': 'Data Center'}
        result = self.normalizer.normalize_row(row)
        self.assertIn('billing_end_before_start', result['flags'])

    def test_high_usage_flagged(self):
        row = {'meter_id': 'MTR-006', 'account_number': 'ACCT-105',
               'billing_start': '2026-03-01', 'billing_end': '2026-03-31',
               'usage_kwh': '520000', 'demand_kw': '1800',
               'tariff': 'Industrial', 'facility': 'Smelting Facility'}
        result = self.normalizer.normalize_row(row)
        self.assertIn('unusually_high_usage', result['flags'])

    def test_missing_meter_flagged(self):
        row = {'meter_id': '', 'account_number': 'ACCT-103',
               'billing_start': '2026-03-01', 'billing_end': '2026-03-31',
               'usage_kwh': '15000', 'demand_kw': '50',
               'tariff': 'Commercial-TOU', 'facility': 'Branch Office'}
        result = self.normalizer.normalize_row(row)
        self.assertIn('missing_meter_id', result['flags'])

    def test_long_billing_period_flagged(self):
        row = {'meter_id': 'MTR-007', 'account_number': 'ACCT-106',
               'billing_start': '2026-02-01', 'billing_end': '2026-04-15',
               'usage_kwh': '45000', 'demand_kw': '130',
               'tariff': 'Industrial', 'facility': 'Remote Facility'}
        result = self.normalizer.normalize_row(row)
        self.assertIn('billing_period_too_long', result['flags'])

    def test_invalid_dates_fail(self):
        row = {'meter_id': 'MTR-001', 'account_number': 'ACCT-100',
               'billing_start': 'bad-date', 'billing_end': '2026-03-31',
               'usage_kwh': '24500'}
        result = self.normalizer.normalize_row(row)
        self.assertIsNotNone(result['error'])


class TravelNormalizerTests(TestCase):
    """Tests for corporate travel normalization."""

    def setUp(self):
        self.normalizer = TravelNormalizer()

    def test_flight_with_known_airports_estimates_distance(self):
        row = {'trip_id': 'TRP-001', 'traveler': 'Test', 'employee_id': 'E1',
               'category': 'Flight', 'booking_date': '2026-03-01',
               'travel_date': '2026-03-10', 'origin': 'DEL', 'destination': 'LHR',
               'distance_km': '', 'hotel_nights': '', 'city': '', 'country': ''}
        result = self.normalizer.normalize_row(row)
        self.assertIsNone(result['error'])
        self.assertEqual(result['fields']['scope'], 'Scope 3')
        self.assertIn('distance_estimated', result['flags'])
        # DEL-LHR is ~6700 km
        self.assertGreater(result['fields']['quantity_normalized'], 6000)
        self.assertLess(result['fields']['quantity_normalized'], 7500)

    def test_flight_with_explicit_distance(self):
        row = {'trip_id': 'TRP-005', 'traveler': 'Test', 'employee_id': 'E2',
               'category': 'Flight', 'travel_date': '2026-03-15',
               'origin': 'JFK', 'destination': 'LAX',
               'distance_km': '3970', 'hotel_nights': '', 'city': '', 'country': ''}
        result = self.normalizer.normalize_row(row)
        self.assertIsNone(result['error'])
        self.assertEqual(result['fields']['quantity_normalized'], 3970)
        self.assertNotIn('distance_estimated', result['flags'])

    def test_invalid_airport_flagged(self):
        row = {'trip_id': 'TRP-008', 'traveler': 'Test', 'employee_id': 'E3',
               'category': 'Flight', 'travel_date': '2026-03-25',
               'origin': 'DEL', 'destination': 'XYZ',
               'distance_km': '', 'hotel_nights': '', 'city': '', 'country': ''}
        result = self.normalizer.normalize_row(row)
        self.assertIn('invalid_destination_airport', result['flags'])

    def test_missing_destination_fails(self):
        row = {'trip_id': 'TRP-011', 'traveler': 'Test', 'employee_id': 'E4',
               'category': 'Flight', 'travel_date': '2026-04-12',
               'origin': 'BOM', 'destination': '',
               'distance_km': '', 'hotel_nights': '', 'city': '', 'country': ''}
        result = self.normalizer.normalize_row(row)
        self.assertIsNotNone(result['error'])
        self.assertIn('missing_destination', result['flags'])

    def test_hotel_normalization(self):
        row = {'trip_id': 'TRP-002', 'traveler': 'Test', 'employee_id': 'E1',
               'category': 'Hotel', 'travel_date': '2026-03-10',
               'origin': '', 'destination': '',
               'distance_km': '', 'hotel_nights': '4', 'city': 'London', 'country': 'UK'}
        result = self.normalizer.normalize_row(row)
        self.assertIsNone(result['error'])
        self.assertEqual(result['fields']['activity_type'], 'Hotel Stay')
        self.assertAlmostEqual(result['fields']['estimated_emissions_kgco2e'], 4 * 20.6, places=1)

    def test_unknown_category_fails(self):
        row = {'trip_id': 'TRP-012', 'traveler': 'Test', 'employee_id': 'E1',
               'category': 'Segway Tour', 'travel_date': '2026-04-15',
               'origin': '', 'destination': '',
               'distance_km': '15', 'hotel_nights': '', 'city': 'London', 'country': 'UK'}
        result = self.normalizer.normalize_row(row)
        self.assertIsNotNone(result['error'])
        self.assertIn('unknown_travel_category', result['flags'])

    def test_taxi_normalization(self):
        row = {'trip_id': 'TRP-006', 'traveler': 'Test', 'employee_id': 'E2',
               'category': 'Taxi', 'travel_date': '2026-03-15',
               'origin': '', 'destination': '',
               'distance_km': '45', 'hotel_nights': '', 'city': 'LA', 'country': 'US'}
        result = self.normalizer.normalize_row(row)
        self.assertIsNone(result['error'])
        self.assertAlmostEqual(result['fields']['estimated_emissions_kgco2e'], 45 * 0.21, places=1)


class ReviewWorkflowTests(TestCase):
    """Tests for the review workflow (approve, reject, lock)."""

    def setUp(self):
        self.client = Client()
        self.tenant = Tenant.objects.create(company_name='Test Corp')
        self.data_source = DataSource.objects.create(
            tenant=self.tenant, source_type='SAP', ingestion_mode='CSV_UPLOAD'
        )
        self.batch = ImportBatch.objects.create(
            tenant=self.tenant, data_source=self.data_source,
            original_filename='test.csv', status='COMPLETED',
            total_rows=1, accepted_rows=1, failed_rows=0
        )
        self.record = EmissionRecord.objects.create(
            tenant=self.tenant, import_batch=self.batch,
            source_type='SAP', activity_type='Diesel Combustion',
            quantity_original=100, unit_original='L',
            quantity_normalized=100, unit_normalized='L',
            scope='Scope 1', review_status='NEEDS_REVIEW',
        )

    def test_approve_record(self):
        response = self.client.post(
            f'/api/records/{self.record.id}/approve/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.review_status, 'APPROVED')

    def test_reject_record(self):
        response = self.client.post(
            f'/api/records/{self.record.id}/reject/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.review_status, 'REJECTED')

    def test_lock_approved_record(self):
        self.record.review_status = 'APPROVED'
        self.record.save()
        response = self.client.post(
            f'/api/records/{self.record.id}/lock/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.review_status, 'LOCKED')
        self.assertIsNotNone(self.record.locked_at)

    def test_cannot_lock_unapproved_record(self):
        response = self.client.post(
            f'/api/records/{self.record.id}/lock/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_locked_record_cannot_be_edited(self):
        self.record.review_status = 'LOCKED'
        self.record.save()
        response = self.client.patch(
            f'/api/records/{self.record.id}/',
            data=json.dumps({'analyst_notes': 'trying to edit'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_locked_record_cannot_be_approved(self):
        self.record.review_status = 'LOCKED'
        self.record.save()
        response = self.client.post(
            f'/api/records/{self.record.id}/approve/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_audit_log_created_on_approve(self):
        self.client.post(
            f'/api/records/{self.record.id}/approve/',
            content_type='application/json'
        )
        logs = AuditLog.objects.filter(emission_record=self.record, action='APPROVED')
        self.assertEqual(logs.count(), 1)
        audit_log = logs.first()
        self.assertEqual(audit_log.before_json['review_status'], 'NEEDS_REVIEW')
        self.assertEqual(audit_log.after_json['review_status'], 'APPROVED')

    def test_audit_log_created_on_reject(self):
        self.client.post(
            f'/api/records/{self.record.id}/reject/',
            content_type='application/json'
        )
        logs = AuditLog.objects.filter(emission_record=self.record, action='REJECTED')
        self.assertEqual(logs.count(), 1)
        audit_log = logs.first()
        self.assertEqual(audit_log.before_json['review_status'], 'NEEDS_REVIEW')
        self.assertEqual(audit_log.after_json['review_status'], 'REJECTED')

    def test_audit_log_created_on_lock(self):
        self.record.review_status = 'APPROVED'
        self.record.save()
        self.client.post(
            f'/api/records/{self.record.id}/lock/',
            content_type='application/json'
        )
        logs = AuditLog.objects.filter(emission_record=self.record, action='LOCKED')
        self.assertEqual(logs.count(), 1)
        audit_log = logs.first()
        self.assertEqual(audit_log.before_json['review_status'], 'APPROVED')
        self.assertEqual(audit_log.after_json['review_status'], 'LOCKED')


class UploadIntegrationTests(TestCase):
    """Integration tests for the CSV upload endpoint."""

    def setUp(self):
        self.client = Client()
        self.tenant = Tenant.objects.create(company_name='Test Corp')

    def test_upload_sap_csv(self):
        csv_content = (
            'BELNR,BUDAT,Werk,MATNR,MAKTX,Menge,MEINS,LIFNR\n'
            '5000001,15.03.2026,PL01,MAT-1001,Diesel Fuel,1200,L,V-2001\n'
            '5000002,2026-03-18,PL01,MAT-1002,Benzin (Petrol),350,liter,V-2002\n'
        )
        file = SimpleUploadedFile('test_sap.csv', csv_content.encode('utf-8'), content_type='text/csv')
        response = self.client.post('/api/upload/', {
            'file': file,
            'source_type': 'SAP',
            'tenant_id': self.tenant.id,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total_rows'], 2)
        self.assertEqual(data['accepted'], 2)
        self.assertEqual(data['failed'], 0)

        # Verify records created
        self.assertEqual(EmissionRecord.objects.filter(tenant=self.tenant).count(), 2)
        self.assertEqual(RawRecord.objects.filter(tenant=self.tenant).count(), 2)
        self.assertEqual(ImportBatch.objects.filter(tenant=self.tenant).count(), 1)

    def test_upload_utility_csv(self):
        csv_content = (
            'meter_id,account_number,billing_start,billing_end,usage_kwh,demand_kw,tariff,facility\n'
            'MTR-001,ACCT-100,2026-03-01,2026-03-31,24500,85,Commercial-TOU,Main Office\n'
        )
        file = SimpleUploadedFile('test_utility.csv', csv_content.encode('utf-8'), content_type='text/csv')
        response = self.client.post('/api/upload/', {
            'file': file,
            'source_type': 'UTILITY',
            'tenant_id': self.tenant.id,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['accepted'], 1)

    def test_upload_travel_csv(self):
        csv_content = (
            'trip_id,traveler,employee_id,category,booking_date,travel_date,origin,destination,distance_km,hotel_nights,city,country\n'
            'TRP-001,Test User,EMP-001,Flight,2026-03-01,2026-03-10,DEL,LHR,,,, \n'
        )
        file = SimpleUploadedFile('test_travel.csv', csv_content.encode('utf-8'), content_type='text/csv')
        response = self.client.post('/api/upload/', {
            'file': file,
            'source_type': 'TRAVEL',
            'tenant_id': self.tenant.id,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['accepted'], 1)

    def test_upload_without_file_returns_error(self):
        response = self.client.post('/api/upload/', {
            'source_type': 'SAP',
            'tenant_id': self.tenant.id,
        })
        self.assertEqual(response.status_code, 400)

    def test_upload_with_invalid_source_returns_error(self):
        csv_content = 'col1,col2\nval1,val2\n'
        file = SimpleUploadedFile('test.csv', csv_content.encode('utf-8'), content_type='text/csv')
        response = self.client.post('/api/upload/', {
            'file': file,
            'source_type': 'INVALID',
            'tenant_id': self.tenant.id,
        })
        self.assertEqual(response.status_code, 400)

    def test_upload_utility_duplicate_detection(self):
        # Upload two identical utility bills in the same file
        csv_content = (
            'meter_id,account_number,billing_start,billing_end,usage_kwh,demand_kw,tariff,facility\n'
            'MTR-999,ACCT-999,2026-03-01,2026-03-31,5000,20,Commercial,Data Center\n'
            'MTR-999,ACCT-999,2026-03-01,2026-03-31,5000,20,Commercial,Data Center\n'
        )
        file = SimpleUploadedFile('test_utility_dupes.csv', csv_content.encode('utf-8'), content_type='text/csv')
        response = self.client.post('/api/upload/', {
            'file': file,
            'source_type': 'UTILITY',
            'tenant_id': self.tenant.id,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total_rows'], 2)
        self.assertEqual(data['accepted'], 2)
        self.assertEqual(data['flagged'], 1)  # The second row is flagged as duplicate

        # Query records in DB (order by ID)
        records = list(EmissionRecord.objects.filter(tenant=self.tenant, source_type='UTILITY').order_by('id'))
        self.assertEqual(len(records), 2)

        # First record: no duplicate flag
        self.assertNotIn('duplicate_meter_period', records[0].flags)
        self.assertEqual(records[0].review_status, 'NEEDS_REVIEW')
        self.assertEqual(records[0].confidence, 'HIGH')

        # Second record: duplicate flag and low confidence
        self.assertIn('duplicate_meter_period', records[1].flags)
        self.assertEqual(records[1].review_status, 'FLAGGED')
        self.assertEqual(records[1].confidence, 'LOW')

        # Upload a third utility bill in a separate file (duplicate against existing DB record)
        csv_content2 = (
            'meter_id,account_number,billing_start,billing_end,usage_kwh,demand_kw,tariff,facility\n'
            'MTR-999,ACCT-999,2026-03-01,2026-03-31,5000,20,Commercial,Data Center\n'
        )
        file2 = SimpleUploadedFile('test_utility_dupe_db.csv', csv_content2.encode('utf-8'), content_type='text/csv')
        response2 = self.client.post('/api/upload/', {
            'file': file2,
            'source_type': 'UTILITY',
            'tenant_id': self.tenant.id,
        })
        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()
        self.assertEqual(data2['accepted'], 1)
        self.assertEqual(data2['flagged'], 1)  # Flagged because it duplicates the DB record

        records = list(EmissionRecord.objects.filter(tenant=self.tenant, source_type='UTILITY').order_by('id'))
        self.assertEqual(len(records), 3)
        self.assertIn('duplicate_meter_period', records[2].flags)
        self.assertEqual(records[2].review_status, 'FLAGGED')
        self.assertEqual(records[2].confidence, 'LOW')
