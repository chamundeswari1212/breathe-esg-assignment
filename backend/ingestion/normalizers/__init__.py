from .sap import SAPNormalizer
from .utility import UtilityNormalizer
from .travel import TravelNormalizer

NORMALIZER_MAP = {
    'SAP': SAPNormalizer,
    'UTILITY': UtilityNormalizer,
    'TRAVEL': TravelNormalizer,
}


def get_normalizer(source_type):
    """Factory: returns the appropriate normalizer class for a source type."""
    normalizer_class = NORMALIZER_MAP.get(source_type)
    if not normalizer_class:
        raise ValueError(f"Unknown source type: {source_type}")
    return normalizer_class()
