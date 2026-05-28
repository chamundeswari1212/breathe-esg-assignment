"""
Base normalizer — shared date parsing, unit normalization, and interface.
Each source normalizer extends this class and implements normalize_row().
"""
import math
from datetime import datetime

from .constants import (
    UNIT_NORMALIZATION,
    UNIT_CONVERSIONS,
    DATE_FORMATS,
    AIRPORT_COORDS,
)


class BaseNormalizer:
    """
    Abstract base for source-specific normalizers.
    Subclasses must implement:
        normalize_row(raw_json: dict) -> dict
    The returned dict should contain fields matching EmissionRecord model.
    """

    def normalize_row(self, raw_json):
        """
        Normalize a single raw row dict into EmissionRecord fields.
        Returns: {
            'fields': dict of EmissionRecord field values,
            'flags': list of flag strings,
            'confidence': 'HIGH' | 'MEDIUM' | 'LOW',
            'error': None or error string (if fatal)
        }
        """
        raise NotImplementedError

    # ----- Shared utilities -----

    @staticmethod
    def parse_date(value):
        """
        Try multiple date formats. Returns datetime.date or None.
        Handles SAP-style YYYYMMDD, European DD.MM.YYYY, ISO, etc.
        """
        if not value or str(value).strip() == '':
            return None

        value_str = str(value).strip()

        for fmt in DATE_FORMATS:
            try:
                return datetime.strptime(value_str, fmt).date()
            except (ValueError, TypeError):
                continue
        return None

    @staticmethod
    def normalize_unit(raw_unit):
        """
        Normalize a raw unit string to a canonical form.
        Returns canonical unit string or None if unknown.
        """
        if not raw_unit:
            return None
        key = str(raw_unit).strip().lower()
        return UNIT_NORMALIZATION.get(key)

    @staticmethod
    def convert_quantity(quantity, from_unit, to_unit):
        """
        Convert quantity between units using known conversion factors.
        Returns converted quantity or None if conversion not available.
        """
        if from_unit == to_unit:
            return quantity
        factor = UNIT_CONVERSIONS.get((from_unit, to_unit))
        if factor:
            return quantity * factor
        # Try reverse
        factor = UNIT_CONVERSIONS.get((to_unit, from_unit))
        if factor:
            return quantity / factor
        return None

    @staticmethod
    def safe_float(value, default=None):
        """Safely parse a float from a string or number."""
        if value is None:
            return default
        try:
            return float(str(value).strip().replace(',', '.'))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def haversine_km(lat1, lon1, lat2, lon2):
        """
        Calculate great-circle distance between two points in km.
        Used for flight distance estimation.
        """
        R = 6371  # Earth's radius in km
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        return R * c

    @classmethod
    def estimate_flight_distance(cls, origin_code, destination_code):
        """
        Estimate flight distance from airport codes using built-in lookup.
        Returns (distance_km, estimated:bool) or (None, False).
        """
        origin = AIRPORT_COORDS.get(str(origin_code).strip().upper())
        dest = AIRPORT_COORDS.get(str(destination_code).strip().upper())
        if origin and dest:
            distance = cls.haversine_km(origin[0], origin[1], dest[0], dest[1])
            return round(distance), True
        return None, False
