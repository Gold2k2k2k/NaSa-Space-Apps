"""Shared, versioned nominal satellite parameters for synthetic/model outputs.

Product-start dates are FIRMS availability examples, not launch dates. The
constellation time offsets are a schematic spacing assumption, not ephemerides.
"""
from datetime import datetime, timezone

SNPP_DATA_END = datetime(2026, 11, 2, 15, 40, tzinfo=timezone.utc)
SATELLITE_REFERENCE_VERSION = "nominal-opportunities-v2"

SATELLITES = [
    {"code": "Terra", "name": "Terra", "norad": 25994, "instrument": "MODIS",
     "resolution_m": 1000, "swath_km": 2330, "altitude_km": 705, "period_min": 98.88,
     "inclination_deg": 98.2, "day_lst_hour": 10.5, "night_lst_hour": 22.5,
     "repeat_days": 16, "phase_offset": 0, "product_start": "2000-11-01"},
    {"code": "Aqua", "name": "Aqua", "norad": 27424, "instrument": "MODIS",
     "resolution_m": 1000, "swath_km": 2330, "altitude_km": 705, "period_min": 98.88,
     "inclination_deg": 98.2, "day_lst_hour": 13.5, "night_lst_hour": 1.5,
     "repeat_days": 16, "phase_offset": 4, "product_start": "2002-07-01"},
    {"code": "N", "name": "Suomi NPP", "norad": 37849, "instrument": "VIIRS",
     "resolution_m": 375, "swath_km": 3060, "altitude_km": 824, "period_min": 101.4,
     "inclination_deg": 98.7, "day_lst_hour": 13.5, "night_lst_hour": 1.5,
     "repeat_days": 16, "phase_offset": 2, "product_start": "2012-01-20"},
    {"code": "N20", "name": "NOAA-20", "norad": 43013, "instrument": "VIIRS",
     "resolution_m": 375, "swath_km": 3060, "altitude_km": 824, "period_min": 101.4,
     "inclination_deg": 98.7, "day_lst_hour": 13.5 + 25 / 60, "night_lst_hour": 1.5 + 25 / 60,
     "repeat_days": 16, "phase_offset": 7, "product_start": "2018-04-01"},
    {"code": "N21", "name": "NOAA-21", "norad": 54234, "instrument": "VIIRS",
     "resolution_m": 375, "swath_km": 3060, "altitude_km": 824, "period_min": 101.4,
     "inclination_deg": 98.7, "day_lst_hour": 13.5 - 25 / 60, "night_lst_hour": 1.5 - 25 / 60,
     "repeat_days": 16, "phase_offset": 11, "product_start": "2024-01-17"},
]
SATELLITES_BY_CODE = {sat["code"]: sat for sat in SATELLITES}
