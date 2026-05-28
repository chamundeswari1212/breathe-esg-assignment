"""
Constants for emission calculations, unit normalization, and reference data.

IMPORTANT: These are PLACEHOLDER emission factors for prototype purposes.
A production system would use a verified emissions factor database such as
DEFRA, EPA, GHG Protocol, or ecoinvent.

Sources for placeholder values:
- UK DEFRA 2023 conversion factors (simplified)
- US EPA eGRID 2022 (simplified national average)
- ICAO Carbon Emissions Calculator methodology (simplified)
"""

# ---------------------------------------------------------------------------
# SAP: Fuel material classification
# ---------------------------------------------------------------------------
# Maps lowercase material keywords → (activity_type, scope, unit_for_factor)
FUEL_MATERIALS = {
    'diesel': ('Diesel Combustion', 'Scope 1', 'L'),
    'dieselkraftstoff': ('Diesel Combustion', 'Scope 1', 'L'),
    'petrol': ('Petrol Combustion', 'Scope 1', 'L'),
    'benzin': ('Petrol Combustion', 'Scope 1', 'L'),
    'gasoline': ('Petrol Combustion', 'Scope 1', 'L'),
    'natural gas': ('Natural Gas Combustion', 'Scope 1', 'M3'),
    'erdgas': ('Natural Gas Combustion', 'Scope 1', 'M3'),
    'lpg': ('LPG Combustion', 'Scope 1', 'L'),
    'flüssiggas': ('LPG Combustion', 'Scope 1', 'L'),
    'heating oil': ('Heating Oil Combustion', 'Scope 1', 'L'),
    'heizöl': ('Heating Oil Combustion', 'Scope 1', 'L'),
    'coal': ('Coal Combustion', 'Scope 1', 'KG'),
    'kohle': ('Coal Combustion', 'Scope 1', 'KG'),
}

# Placeholder emission factors: kgCO2e per unit
# Source: Simplified from UK DEFRA 2023 GHG Conversion Factors
FUEL_EMISSION_FACTORS = {
    'Diesel Combustion': {'factor': 2.68, 'unit': 'L', 'source': 'DEFRA 2023 (simplified)'},
    'Petrol Combustion': {'factor': 2.31, 'unit': 'L', 'source': 'DEFRA 2023 (simplified)'},
    'Natural Gas Combustion': {'factor': 2.02, 'unit': 'M3', 'source': 'DEFRA 2023 (simplified)'},
    'LPG Combustion': {'factor': 1.51, 'unit': 'L', 'source': 'DEFRA 2023 (simplified)'},
    'Heating Oil Combustion': {'factor': 2.54, 'unit': 'L', 'source': 'DEFRA 2023 (simplified)'},
    'Coal Combustion': {'factor': 2.42, 'unit': 'KG', 'source': 'DEFRA 2023 (simplified)'},
}

# ---------------------------------------------------------------------------
# SAP: Column name aliases (German → English mapping)
# SAP systems often export with German field names
# ---------------------------------------------------------------------------
SAP_COLUMN_ALIASES = {
    # Document number
    'belnr': 'document_number', 'belegnummer': 'document_number',
    'doc_number': 'document_number', 'document_number': 'document_number',
    # Posting date
    'budat': 'posting_date', 'buchungsdatum': 'posting_date',
    'posting_date': 'posting_date', 'date': 'posting_date',
    # Plant
    'werk': 'plant_code', 'plant': 'plant_code', 'plant_code': 'plant_code',
    # Material number
    'matnr': 'material_number', 'materialnummer': 'material_number',
    'material_number': 'material_number', 'material_no': 'material_number',
    # Material description
    'maktx': 'material_description', 'material': 'material_description',
    'materialkurztext': 'material_description', 'material_description': 'material_description',
    'description': 'material_description',
    # Quantity
    'menge': 'quantity', 'quantity': 'quantity', 'qty': 'quantity',
    # Unit of measure
    'meins': 'unit', 'mengeneinheit': 'unit', 'unit': 'unit', 'uom': 'unit',
    # Vendor
    'lifnr': 'vendor', 'lieferant': 'vendor', 'vendor': 'vendor',
    'supplier': 'vendor',
}

# ---------------------------------------------------------------------------
# Unit normalization
# ---------------------------------------------------------------------------
UNIT_NORMALIZATION = {
    # Volume → L (liters)
    'l': 'L', 'liter': 'L', 'litre': 'L', 'ltr': 'L', 'liters': 'L', 'litres': 'L',
    # Mass → KG
    'kg': 'KG', 'kilogram': 'KG', 'kilogramm': 'KG', 'kilograms': 'KG',
    # Mass → T (metric tonnes) — we keep as T, convert to KG when needed
    'to': 'T', 't': 'T', 'tonne': 'T', 'tonnes': 'T', 'ton': 'T', 'mt': 'T',
    # Volume → M3
    'm3': 'M3', 'm³': 'M3', 'cbm': 'M3', 'cubic meter': 'M3',
    # Energy
    'kwh': 'KWH', 'mwh': 'MWH',
    # Distance
    'km': 'KM', 'mi': 'MI', 'miles': 'MI',
    # Count
    'nights': 'NIGHTS', 'night': 'NIGHTS',
    'trip': 'TRIP', 'trips': 'TRIP',
}

# Conversion factors to base units for emission calculation
UNIT_CONVERSIONS = {
    ('T', 'KG'): 1000.0,    # 1 tonne = 1000 kg
    ('MWH', 'KWH'): 1000.0, # 1 MWh = 1000 kWh
    ('MI', 'KM'): 1.60934,  # 1 mile = 1.609 km
}

# ---------------------------------------------------------------------------
# Utility: Electricity emission factor
# ---------------------------------------------------------------------------
# US national grid average, simplified
# Source: EPA eGRID 2022 national average
ELECTRICITY_EMISSION_FACTOR = {
    'factor': 0.417,  # kgCO2e per kWh
    'unit': 'KWH',
    'source': 'EPA eGRID 2022 national average (simplified)',
}

# Thresholds for suspicious usage detection
UTILITY_HIGH_USAGE_KWH = 100000   # Flag if single billing period > 100 MWh
UTILITY_LOW_USAGE_KWH = 10        # Flag if single billing period < 10 kWh
UTILITY_MAX_BILLING_DAYS = 45     # Flag if billing period > 45 days

# ---------------------------------------------------------------------------
# Travel: Emission factors
# ---------------------------------------------------------------------------
TRAVEL_EMISSION_FACTORS = {
    'flight': {'factor': 0.255, 'unit': 'passenger-km', 'source': 'DEFRA 2023 avg economy (simplified)'},
    'hotel': {'factor': 20.6, 'unit': 'night', 'source': 'Cornell Hotel Sustainability Benchmarking (simplified)'},
    'rail': {'factor': 0.041, 'unit': 'passenger-km', 'source': 'DEFRA 2023 national rail (simplified)'},
    'taxi': {'factor': 0.21, 'unit': 'km', 'source': 'DEFRA 2023 average car (simplified)'},
    'rideshare': {'factor': 0.21, 'unit': 'km', 'source': 'DEFRA 2023 average car (simplified)'},
}

# Travel category normalization
TRAVEL_CATEGORY_ALIASES = {
    'flight': 'flight', 'flights': 'flight', 'air': 'flight', 'airfare': 'flight',
    'hotel': 'hotel', 'hotels': 'hotel', 'lodging': 'hotel', 'accommodation': 'hotel',
    'rail': 'rail', 'train': 'rail', 'railway': 'rail',
    'taxi': 'taxi', 'cab': 'taxi', 'rideshare': 'rideshare', 'ride': 'rideshare',
    'uber': 'rideshare', 'lyft': 'rideshare', 'car rental': 'car_rental',
    'rental car': 'car_rental', 'car': 'car_rental',
}

# ---------------------------------------------------------------------------
# Airport lookup for flight distance estimation
# Approximate great-circle distances in km for common routes.
# Used when distance_km is missing but origin/destination airports are known.
# Source: gcmap.com / Great Circle Mapper
# ---------------------------------------------------------------------------
AIRPORT_COORDS = {
    # Code: (latitude, longitude)  — approximate
    'DEL': (28.556, 77.100),    # New Delhi
    'BOM': (19.089, 72.869),    # Mumbai
    'BLR': (13.199, 77.707),    # Bangalore
    'MAA': (12.990, 80.169),    # Chennai
    'HYD': (17.240, 78.430),    # Hyderabad
    'CCU': (22.655, 88.447),    # Kolkata
    'LHR': (51.470, -0.461),    # London Heathrow
    'JFK': (40.640, -73.779),   # New York JFK
    'LAX': (33.943, -118.408),  # Los Angeles
    'SFO': (37.619, -122.375),  # San Francisco
    'ORD': (41.978, -87.904),   # Chicago O'Hare
    'SIN': (1.350, 103.994),    # Singapore
    'DXB': (25.253, 55.365),    # Dubai
    'FRA': (50.033, 8.571),     # Frankfurt
    'CDG': (49.010, 2.548),     # Paris CDG
    'NRT': (35.764, 140.386),   # Tokyo Narita
    'HKG': (22.309, 113.915),   # Hong Kong
    'SYD': (-33.946, 151.177),  # Sydney
    'YYZ': (43.677, -79.631),   # Toronto
    'AMS': (52.309, 4.764),     # Amsterdam
    'MUC': (48.354, 11.786),    # Munich
    'ICN': (37.469, 126.451),   # Seoul Incheon
    'PEK': (40.080, 116.585),   # Beijing
    'DOH': (25.261, 51.565),    # Doha
}

# Set of valid IATA codes for validation
VALID_AIRPORT_CODES = set(AIRPORT_COORDS.keys())

# ---------------------------------------------------------------------------
# Common date formats to try when parsing dates
# ---------------------------------------------------------------------------
DATE_FORMATS = [
    '%Y-%m-%d',     # 2026-05-20
    '%d-%m-%Y',     # 20-05-2026
    '%d.%m.%Y',     # 20.05.2026  (German/EU)
    '%Y/%m/%d',     # 2026/05/20
    '%d/%m/%Y',     # 20/05/2026
    '%m/%d/%Y',     # 05/20/2026 (US)
    '%Y%m%d',       # 20260520  (SAP internal)
    '%d-%m-%y',     # 20-05-26
    '%m-%d-%Y',     # 05-20-2026
]
