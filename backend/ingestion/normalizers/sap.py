"""
SAP Fuel & Procurement normalizer.

Handles flat CSV exports from SAP MM (Materials Management) module.
Maps German column aliases to canonical names, classifies fuel vs non-fuel
materials, and normalizes units.

Design decision: We chose flat CSV export as the ingestion format because
SAP IDoc/OData/BAPI integration requires SAP middleware and authentication
infrastructure that is not feasible in a 4-day prototype. Flat CSV export
is a realistic first step — many organizations extract SAP data this way.
"""
from .base import BaseNormalizer
from .constants import (
    SAP_COLUMN_ALIASES,
    FUEL_MATERIALS,
    FUEL_EMISSION_FACTORS,
)


class SAPNormalizer(BaseNormalizer):

    def normalize_row(self, raw_json):
        """
        Normalize a single SAP fuel/procurement CSV row.

        Expected columns (or German aliases):
            BELNR, BUDAT, Werk, MATNR, MAKTX, Menge, MEINS, LIFNR
        """
        flags = []
        confidence = 'HIGH'

        # Step 1: Map column aliases to canonical names
        mapped = self._map_columns(raw_json)

        # Step 2: Extract fields
        document_number = str(mapped.get('document_number', '')).strip()
        posting_date_raw = str(mapped.get('posting_date', '')).strip()
        plant_code = str(mapped.get('plant_code', '')).strip()
        material_number = str(mapped.get('material_number', '')).strip()
        material_desc = str(mapped.get('material_description', '')).strip()
        quantity_raw = mapped.get('quantity', '')
        unit_raw = str(mapped.get('unit', '')).strip()
        vendor = str(mapped.get('vendor', '')).strip()

        # Step 3: Parse date
        posting_date = self.parse_date(posting_date_raw)
        if not posting_date:
            flags.append('date_parse_failure')
            confidence = 'LOW'

        # Step 4: Parse quantity
        quantity = self.safe_float(quantity_raw)
        if quantity is None:
            return {
                'fields': None,
                'flags': flags,
                'confidence': confidence,
                'error': f"Cannot parse quantity: '{quantity_raw}'"
            }

        if quantity == 0:
            flags.append('zero_quantity')
            confidence = 'LOW'
        elif quantity < 0:
            flags.append('negative_quantity')
            confidence = 'LOW'

        # Step 5: Normalize unit
        unit_normalized = self.normalize_unit(unit_raw)
        if not unit_normalized:
            flags.append('unknown_unit')
            confidence = 'LOW'
            unit_normalized = unit_raw.upper() if unit_raw else 'UNKNOWN'

        # Step 6: Check plant
        if not plant_code:
            flags.append('missing_plant')
            confidence = min(confidence, 'MEDIUM') if confidence == 'HIGH' else confidence

        # Step 7: Classify material as fuel or non-fuel
        fuel_info = self._classify_material(material_desc)

        if fuel_info:
            activity_type, scope, factor_unit = fuel_info
            # Attempt unit conversion if needed
            quantity_for_factor = quantity
            if unit_normalized != factor_unit:
                converted = self.convert_quantity(quantity, unit_normalized, factor_unit)
                if converted is not None:
                    quantity_for_factor = converted
                else:
                    flags.append('unit_conversion_needed')
                    confidence = 'MEDIUM' if confidence == 'HIGH' else confidence

            # Calculate estimated emissions
            factor_info = FUEL_EMISSION_FACTORS.get(activity_type, {})
            emission_factor = factor_info.get('factor', 0)
            factor_source = factor_info.get('source', 'unknown')
            estimated_emissions = abs(quantity_for_factor) * emission_factor

            category = 'fuel_combustion'
        else:
            # Non-fuel procurement item
            activity_type = f"Procurement: {material_desc}" if material_desc else 'Unknown Procurement'
            scope = 'Scope 3'  # Upstream purchased goods
            estimated_emissions = None
            factor_source = 'N/A — non-fuel procurement, no factor applied'
            category = 'purchased_goods'
            flags.append('procurement_not_fuel')
            confidence = 'LOW'

        # Step 8: Check for unknown material
        if not material_desc or material_desc.lower().startswith('unknown'):
            flags.append('unknown_material')
            confidence = 'LOW'

        fields = {
            'source_type': 'SAP',
            'source_record_id': document_number,
            'activity_type': activity_type,
            'category': category,
            'period_start': posting_date,
            'period_end': posting_date,
            'quantity_original': quantity,
            'unit_original': unit_raw or 'UNKNOWN',
            'quantity_normalized': abs(quantity),
            'unit_normalized': unit_normalized,
            'scope': scope,
            'location_details': {
                'plant_code': plant_code,
                'material_number': material_number,
                'vendor': vendor,
            },
            'emission_factor_source': factor_source,
            'estimated_emissions_kgco2e': round(estimated_emissions, 2) if estimated_emissions else None,
        }

        return {
            'fields': fields,
            'flags': flags,
            'confidence': confidence,
            'error': None,
        }

    def _map_columns(self, raw_json):
        """Map German/varied column names to canonical English names."""
        mapped = {}
        for key, value in raw_json.items():
            canonical = SAP_COLUMN_ALIASES.get(key.lower().strip(), key.lower().strip())
            mapped[canonical] = value
        return mapped

    def _classify_material(self, material_desc):
        """
        Classify material description as fuel or non-fuel.
        Returns (activity_type, scope, factor_unit) or None.
        """
        if not material_desc:
            return None
        desc_lower = material_desc.lower()
        for keyword, info in FUEL_MATERIALS.items():
            if keyword in desc_lower:
                return info
        return None
