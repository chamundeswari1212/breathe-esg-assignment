"""
Corporate Travel normalizer.

Handles CSV exports from corporate travel platforms (Concur, Navan, etc.).
Normalizes flights, hotels, rail, and ground transport to Scope 3 emissions.

Design decision: We chose corporate travel platform CSV export (inspired by
Concur/Navan) because it is the most common format travel managers work with.
Direct API integration requires OAuth and vendor contracts not feasible
in a 4-day prototype.
"""
from .base import BaseNormalizer
from .constants import (
    TRAVEL_EMISSION_FACTORS,
    TRAVEL_CATEGORY_ALIASES,
    VALID_AIRPORT_CODES,
)


class TravelNormalizer(BaseNormalizer):

    def normalize_row(self, raw_json):
        """
        Normalize a single corporate travel CSV row.

        Expected columns:
            trip_id, traveler, employee_id, category, booking_date,
            travel_date, origin, destination, distance_km, hotel_nights,
            city, country
        """
        flags = []
        confidence = 'HIGH'

        # Step 1: Extract fields
        trip_id = str(raw_json.get('trip_id', '')).strip()
        traveler = str(raw_json.get('traveler', '')).strip()
        employee_id = str(raw_json.get('employee_id', '')).strip()
        category_raw = str(raw_json.get('category', '')).strip()
        booking_date_raw = str(raw_json.get('booking_date', '')).strip()
        travel_date_raw = str(raw_json.get('travel_date', '')).strip()
        origin = str(raw_json.get('origin', '')).strip().upper()
        destination = str(raw_json.get('destination', '')).strip().upper()
        distance_raw = raw_json.get('distance_km', '')
        hotel_nights_raw = raw_json.get('hotel_nights', '')
        city = str(raw_json.get('city', '')).strip()
        country = str(raw_json.get('country', '')).strip()

        # Step 2: Parse travel date
        travel_date = self.parse_date(travel_date_raw)
        booking_date = self.parse_date(booking_date_raw)
        if not travel_date:
            flags.append('date_parse_failure')
            confidence = 'MEDIUM'

        # Step 3: Normalize category
        category_normalized = TRAVEL_CATEGORY_ALIASES.get(category_raw.lower())
        if not category_normalized:
            flags.append('unknown_travel_category')
            return {
                'fields': None,
                'flags': flags,
                'confidence': 'LOW',
                'error': f"Unknown travel category: '{category_raw}'"
            }

        # Step 4: Category-specific normalization
        if category_normalized == 'flight':
            result = self._normalize_flight(
                origin, destination, distance_raw, flags, confidence
            )
        elif category_normalized == 'hotel':
            result = self._normalize_hotel(
                hotel_nights_raw, city, country, flags, confidence
            )
        elif category_normalized in ('rail',):
            result = self._normalize_rail(
                distance_raw, city, flags, confidence
            )
        elif category_normalized in ('taxi', 'rideshare'):
            result = self._normalize_ground(
                category_normalized, distance_raw, city, flags, confidence
            )
        else:
            return {
                'fields': None,
                'flags': flags + ['unsupported_category'],
                'confidence': 'LOW',
                'error': f"Category '{category_normalized}' not yet supported for emission calculation"
            }

        if result.get('error'):
            return result

        # Merge common fields
        fields = result['fields']
        fields.update({
            'source_type': 'TRAVEL',
            'source_record_id': trip_id,
            'period_start': travel_date,
            'period_end': travel_date,
            'scope': 'Scope 3',
            'location_details': {
                'traveler': traveler,
                'employee_id': employee_id,
                'origin': origin if origin else None,
                'destination': destination if destination else None,
                'city': city if city else None,
                'country': country if country else None,
            },
        })

        return {
            'fields': fields,
            'flags': result['flags'],
            'confidence': result['confidence'],
            'error': None,
        }

    def _normalize_flight(self, origin, destination, distance_raw, flags, confidence):
        """Normalize a flight row."""
        distance_km = self.safe_float(distance_raw)
        estimated = False

        # Validate airports
        if not destination:
            flags.append('missing_destination')
            confidence = 'LOW'
            return {
                'fields': None,
                'flags': flags,
                'confidence': confidence,
                'error': 'Flight missing destination airport'
            }

        if origin and origin not in VALID_AIRPORT_CODES:
            flags.append('invalid_origin_airport')
            confidence = 'MEDIUM'

        if destination not in VALID_AIRPORT_CODES:
            flags.append('invalid_destination_airport')
            confidence = 'LOW'

        # Estimate distance if missing
        if not distance_km and origin and destination:
            distance_km, estimated = self.estimate_flight_distance(origin, destination)
            if estimated:
                flags.append('distance_estimated')
                confidence = 'MEDIUM' if confidence == 'HIGH' else confidence
            else:
                flags.append('missing_distance')
                confidence = 'LOW'

        if not distance_km:
            flags.append('missing_distance')
            confidence = 'LOW'
            # Use a fallback so we can still create the record
            distance_km = 0

        factor_info = TRAVEL_EMISSION_FACTORS['flight']
        estimated_emissions = abs(distance_km) * factor_info['factor']

        return {
            'fields': {
                'activity_type': 'Flight',
                'category': 'business_travel_flight',
                'quantity_original': distance_km,
                'unit_original': 'km' if not estimated else 'km (estimated)',
                'quantity_normalized': abs(distance_km),
                'unit_normalized': 'KM',
                'emission_factor_source': factor_info['source'],
                'estimated_emissions_kgco2e': round(estimated_emissions, 2),
            },
            'flags': flags,
            'confidence': confidence,
            'error': None,
        }

    def _normalize_hotel(self, nights_raw, city, country, flags, confidence):
        """Normalize a hotel stay row."""
        nights = self.safe_float(nights_raw)

        if not nights or nights <= 0:
            flags.append('missing_hotel_nights')
            confidence = 'LOW'
            nights = nights or 0

        factor_info = TRAVEL_EMISSION_FACTORS['hotel']
        estimated_emissions = abs(nights) * factor_info['factor']

        return {
            'fields': {
                'activity_type': 'Hotel Stay',
                'category': 'business_travel_hotel',
                'quantity_original': nights,
                'unit_original': 'nights',
                'quantity_normalized': abs(nights),
                'unit_normalized': 'NIGHTS',
                'emission_factor_source': factor_info['source'],
                'estimated_emissions_kgco2e': round(estimated_emissions, 2),
            },
            'flags': flags,
            'confidence': confidence,
            'error': None,
        }

    def _normalize_rail(self, distance_raw, route_desc, flags, confidence):
        """Normalize a rail journey row."""
        distance_km = self.safe_float(distance_raw)

        if not distance_km or distance_km <= 0:
            flags.append('missing_distance')
            confidence = 'MEDIUM'
            distance_km = distance_km or 0

        factor_info = TRAVEL_EMISSION_FACTORS['rail']
        estimated_emissions = abs(distance_km) * factor_info['factor']

        return {
            'fields': {
                'activity_type': 'Rail Journey',
                'category': 'business_travel_rail',
                'quantity_original': distance_km,
                'unit_original': 'km',
                'quantity_normalized': abs(distance_km),
                'unit_normalized': 'KM',
                'emission_factor_source': factor_info['source'],
                'estimated_emissions_kgco2e': round(estimated_emissions, 2),
            },
            'flags': flags,
            'confidence': confidence,
            'error': None,
        }

    def _normalize_ground(self, category, distance_raw, city, flags, confidence):
        """Normalize a taxi/rideshare journey."""
        distance_km = self.safe_float(distance_raw)

        if not distance_km or distance_km <= 0:
            flags.append('missing_distance')
            confidence = 'MEDIUM'
            distance_km = distance_km or 0

        factor_key = 'taxi' if category == 'taxi' else 'rideshare'
        factor_info = TRAVEL_EMISSION_FACTORS.get(factor_key, TRAVEL_EMISSION_FACTORS['taxi'])
        estimated_emissions = abs(distance_km) * factor_info['factor']

        return {
            'fields': {
                'activity_type': f"{category.title()} Journey",
                'category': f'business_travel_{category}',
                'quantity_original': distance_km,
                'unit_original': 'km',
                'quantity_normalized': abs(distance_km),
                'unit_normalized': 'KM',
                'emission_factor_source': factor_info['source'],
                'estimated_emissions_kgco2e': round(estimated_emissions, 2),
            },
            'flags': flags,
            'confidence': confidence,
            'error': None,
        }
