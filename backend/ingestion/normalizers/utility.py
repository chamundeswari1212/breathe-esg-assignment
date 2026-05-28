"""
Utility Electricity normalizer.

Handles portal CSV exports from utility companies (e.g., Duke Energy, PG&E).
Normalizes electricity usage to Scope 2 emissions.

Design decision: We chose utility portal CSV export because facilities teams
commonly download billing data from their utility's web portal. This is the
most realistic and accessible data format for a prototype.
"""
from datetime import timedelta

from .base import BaseNormalizer
from .constants import (
    ELECTRICITY_EMISSION_FACTOR,
    UTILITY_HIGH_USAGE_KWH,
    UTILITY_LOW_USAGE_KWH,
    UTILITY_MAX_BILLING_DAYS,
)


class UtilityNormalizer(BaseNormalizer):

    def normalize_row(self, raw_json):
        """
        Normalize a single utility electricity CSV row.

        Expected columns:
            meter_id, account_number, billing_start, billing_end,
            usage_kwh, demand_kw, tariff, facility
        """
        flags = []
        confidence = 'HIGH'

        # Step 1: Extract fields
        meter_id = str(raw_json.get('meter_id', '')).strip()
        account_number = str(raw_json.get('account_number', '')).strip()
        billing_start_raw = str(raw_json.get('billing_start', '')).strip()
        billing_end_raw = str(raw_json.get('billing_end', '')).strip()
        usage_raw = raw_json.get('usage_kwh', '')
        demand_raw = raw_json.get('demand_kw', '')
        tariff = str(raw_json.get('tariff', '')).strip()
        facility = str(raw_json.get('facility', '')).strip()

        # Step 2: Parse dates
        billing_start = self.parse_date(billing_start_raw)
        billing_end = self.parse_date(billing_end_raw)

        if not billing_start or not billing_end:
            return {
                'fields': None,
                'flags': flags,
                'confidence': confidence,
                'error': f"Cannot parse billing dates: start='{billing_start_raw}', end='{billing_end_raw}'"
            }

        # Step 3: Validate billing period
        if billing_end < billing_start:
            flags.append('billing_end_before_start')
            confidence = 'LOW'

        billing_days = (billing_end - billing_start).days
        if billing_days > UTILITY_MAX_BILLING_DAYS:
            flags.append('billing_period_too_long')
            confidence = 'MEDIUM' if confidence == 'HIGH' else confidence

        # Step 4: Parse usage
        usage_kwh = self.safe_float(usage_raw)
        if usage_kwh is None:
            return {
                'fields': None,
                'flags': flags,
                'confidence': confidence,
                'error': f"Cannot parse usage_kwh: '{usage_raw}'"
            }

        # Step 5: Check usage thresholds
        if usage_kwh > UTILITY_HIGH_USAGE_KWH:
            flags.append('unusually_high_usage')
            confidence = 'MEDIUM' if confidence == 'HIGH' else confidence

        if 0 < usage_kwh < UTILITY_LOW_USAGE_KWH:
            flags.append('unusually_low_usage')
            confidence = 'MEDIUM' if confidence == 'HIGH' else confidence

        if usage_kwh <= 0:
            flags.append('zero_or_negative_usage')
            confidence = 'LOW'

        # Step 6: Check meter ID
        if not meter_id:
            flags.append('missing_meter_id')
            confidence = 'MEDIUM' if confidence == 'HIGH' else confidence

        # Step 7: Calculate emissions
        factor = ELECTRICITY_EMISSION_FACTOR['factor']
        factor_source = ELECTRICITY_EMISSION_FACTOR['source']
        estimated_emissions = abs(usage_kwh) * factor

        # Parse demand
        demand_kw = self.safe_float(demand_raw)

        fields = {
            'source_type': 'UTILITY',
            'source_record_id': f"{meter_id}_{billing_start_raw}_{billing_end_raw}",
            'activity_type': 'Grid Electricity',
            'category': 'purchased_electricity',
            'period_start': billing_start,
            'period_end': billing_end,
            'quantity_original': usage_kwh,
            'unit_original': 'kWh',
            'quantity_normalized': abs(usage_kwh),
            'unit_normalized': 'KWH',
            'scope': 'Scope 2',
            'location_details': {
                'meter_id': meter_id,
                'account_number': account_number,
                'facility': facility,
                'tariff': tariff,
                'demand_kw': demand_kw,
            },
            'emission_factor_source': factor_source,
            'estimated_emissions_kgco2e': round(estimated_emissions, 2),
        }

        return {
            'fields': fields,
            'flags': flags,
            'confidence': confidence,
            'error': None,
        }
