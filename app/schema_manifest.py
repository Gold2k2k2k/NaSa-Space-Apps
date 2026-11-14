"""Human-readable logical evidence views; these are not database tables."""
from __future__ import annotations

_COMMON = {
    "latitude": "required finite degrees [-90,90]",
    "longitude": "required finite degrees [-180,180]",
    "scan": "optional positive km; missing uses a flagged nominal default",
    "track": "optional positive km; missing uses a flagged nominal default",
    "acq_date": "required ISO YYYY-MM-DD",
    "acq_time": "optional HHMM UTC; missing retains date-only precision",
    "instrument": "MODIS or VIIRS; compatible satellite aliases are normalized",
    "version": "optional supplied processing label; not authenticated",
    "frp": "nullable nonnegative MW; measured zero is preserved",
    "daynight": "D or N; missing becomes U (unknown)",
    "type": "0 presumed vegetation, 1 volcano, 2 other static land, 3 offshore; missing defaults to 0",
}
SOURCE_SCHEMAS = {
    "firms_modis_c61": {
        "description": "FIRMS MODIS Collection 6.1; demo availability starts 2000-11-01; nominal 1000 m",
        "fields": {**_COMMON, "brightness": "nullable MIR brightness temperature K",
                   "bright_t31": "nullable TIR brightness temperature K",
                   "satellite": "Terra/T or Aqua/A", "confidence": "0..100; <30 low, <80 nominal, otherwise high"},
    },
    "firms_viirs_snpp": {
        "description": "FIRMS S-NPP VIIRS 375 m; demo delivery 2012-01-20 to 2026-11-02 15:40 UTC",
        "fields": {**_COMMON, "bright_ti4": "nullable MIR brightness temperature K",
                   "bright_ti5": "nullable TIR brightness temperature K",
                   "satellite": "N, S-NPP or Suomi NPP", "confidence": "l/n/h or low/nominal/high"},
    },
    "firms_viirs_noaa20_21": {
        "description": "FIRMS NOAA-20 and NOAA-21 VIIRS 375 m; demo starts 2018-04-01 and 2024-01-17",
        "fields": {**_COMMON, "bright_ti4": "nullable MIR brightness temperature K",
                   "bright_ti5": "nullable TIR brightness temperature K",
                   "satellite": "N20/J1/1/NOAA-20 or N21/J2/2/NOAA-21", "confidence": "l/n/h or low/nominal/high"},
    },
}


def _fields(names, description):
    return dict.fromkeys(names.split(), description)


TARGET_SCHEMAS = {
    "harmonized_hotspots": {
        **_fields("hotspot_id cell_id", "string; canonical event ID or 1000 m sinusoidal target bin"),
        **_fields("lat lon", "finite degrees; circular weighted centroid or observed point fallback"),
        "point_method": "weighted centroid or observed point fallback when centroid is outside the AOI",
        **_fields("acq_date year month dekad observation_dates", "UTC date keys; dekad 1..36; dates retained across midnight"),
        **_fields("daynight temporal_precision window_start_utc window_end_utc", "D/N/U; timestamped anchored 60-minute or source-separated date-only window; timestamps nullable"),
        **_fields("sensor_family satellites", "family and distinct satellite provenance"),
        **_fields("mir_bt_k tir_bt_k", "nullable observed brightness temperature K"),
        **_fields("confidence_class confidence_weight", "heuristic class and weight: unknown 0, low .45, nominal .80, high 1; not probability"),
        "effective_area_km2": "mean scan * track metadata; not burned area or an occupancy weight",
        "footprint_basis": "supplied_dimensions or contains_nominal_defaults (MODIS 1 km / VIIRS .375 km per dimension)",
        **_fields("raw_detections unique_observations duplicate_observation_rows raw_modis raw_viirs", "integer retained-row, unique identity, revision duplicate and sensor counts"),
        **_fields("modis_w viirs_w modis_satellite_factor viirs_satellite_factor overpass_dedup_factor", "family mean confidence occupancy and diagnostic satellite averaging factors"),
        **_fields("modis_frp_mw viirs_frp_mw hfre_mw", "nullable summed observed power MW with satellite means and optional bridge; not energy"),
        **_fields("fire_category source_type classification_basis", "supplied source type or descriptive pattern; no validated fire cause"),
        "is_flare": "boolean legacy alias for supplied non-vegetation types 1..3, not just flares",
        "is_persistent_inferred": "boolean multi-year occupancy flag; does not establish cause or auto-exclude vegetation",
        **_fields("frp_observation_count frp_is_missing", "observed power count and missingness flag"),
        "include_in_calendar": "boolean; guard excludes supplied types 1..3 while retaining evidence",
        "hhe": "weighted cell-window occupancy contribution; monthly family blend; not fire count",
    },
    "burning_calendar_cells": {
        **_fields("aoi_id year month month_name", "AOI and month coordinates within selected 2000..2026 window"),
        **_fields("is_observed is_complete coverage_status", "boolean flags and missing / records_only / complete; absent is zero only under declared complete coverage"),
        **_fields("value hhe_total raw_total raw_modis raw_viirs", "nullable active metric, HHE or retained detection counts; not physical fire counts"),
        "frp_total_mw": "nullable summed observed power MW across events, not energy or simultaneous regional power",
        **_fields("frp_measured_events frp_missing_events", "integer measured and missing contribution counts"),
        "night_share": "nullable activity fraction among known D/N observations; unknowns excluded",
        **_fields("hist_median_hhe hist_mean_hhe hist_iqr_hhe hist_p90_hhe hist_p95_hhe", "nullable same-month active-metric statistics in 2001..2020; legacy hhe suffix also used in raw mode"),
        **_fields("anomaly_abs anomaly_pct z_robust empirical_percentile", "nullable difference, percent change, heuristic Z and empirical midrank; Z scale max(.7413*IQR,.5,0.18*median)"),
        "severity_band": "descriptive tier or missing",
        **_fields("observed_value value_is_counterfactual", "optional hypothetical metric labels; observations and reference held fixed"),
    },
    "fire_regime_summaries": {
        **_fields("peak_months peak_month_names", "baseline seasonal peak months and labels; not forecasts"),
        **_fields("peak_year peak_year_value peak_month_record", "nullable maximum complete-year total and maximum observed month record"),
        **_fields("trend_slope_per_decade theil_sen_slope_per_decade harmonized_trend_slope_per_decade raw_trend_slope_per_decade", "nullable OLS or named Theil-Sen slopes using complete years, index units per decade"),
        "trend_complete_year_count": "integer number of complete annual totals used",
    },
    "sensor_calibration_audit": {
        **_fields("aoi_id method_version overlap_years", "AOI, original demo method version and February 2012..December 2024 overlap"),
        **_fields("overlap_months_count calibration_valid calibration_basis", "matched positive monthly count; pooled fit needs >=3 months, otherwise assumed .58"),
        **_fields("raw_viirs_to_modis_ratio calibrated_kappa", "nullable raw ratio; kappa=sum(M occupancy)/sum(V occupancy), or labeled assumption"),
        **_fields("frp_conversion_ratio frp_calibration_basis matched_frp_windows", "positive matched-window sum ratio needs >=3 windows; otherwise assumed identity 1"),
        "era_diagnostics": "2012..2017, 2018..2023, 2024 descriptive ratios and agreement under pooled multiplier",
        **_fields("bridge_r2 bridge_efficiency bridge_rmse bridge_mean_bias", "nullable in-sample squared correlation, 1-SSE/SST, RMSE and mean bias; not external validation"),
        **_fields("overpass_duplicates_removed exact_or_revised_duplicate_rows", "integer row-to-window reductions and exact/revision duplicate counts; not independently verified same-fire observations"),
        **_fields("raw_step_jump_2012_pct harmonized_step_diff_2012_pct bias_reduction_pct transition_audits", "nullable three-complete-year pre/post diagnostics (2012 and 2018); reduction can be negative"),
        **_fields("total_raw_detections total_harmonized_events skipped_invalid_rows", "integer selected valid rows, retained windows and rejected normalization rows"),
        **_fields("static_flare_detections flare_contamination_share non_vegetation_share", "legacy aliases and fraction for supplied non-vegetation types 1..3; not industrial cause attribution"),
        **_fields("wildfire_share agricultural_share category_counts classification_limit", "descriptive pattern counts/shares with legacy names; no cause validation"),
        "quality": "pre-confidence-filter valid in-AOI measurement missing counts and row selection diagnostics",
        "exclude_static_flares": "boolean legacy option name; guard for supplied types 1..3",
        "window_minutes": "60; anchored timestamped windows, date-only source groups separate",
        "target_grid_metres": "1000; MODIS-sphere sinusoidal target bins, not native tile pixels",
    },
}

MAPPING_MANIFESTO = [
    {
        "target_table": "harmonized_hotspots",
        "anchor_source": "Union of normalized FIRMS-shaped MODIS and VIIRS rows",
        "join_paths": ["Filter full AOI geometry and confidence; retain source/quality diagnostics",
                       "Group sinusoidal cell, day/night and supplied type into anchored 60-minute windows",
                       "Prefer supplied standard processing over NRT/RT/URT revisions; average satellite occupancy within each family"],
        "fields": [
            {"target": "hhe", "source": "M, kappa*V or half their sum in dual-family months", "type": "Demo index", "rationale": "Avoid additive same-cell occupancy; not a fire count or footprint correction"},
            {"target": "footprint_basis, effective_area_km2", "source": "supplied scan * track or flagged nominal dimensions", "type": "Metadata", "rationale": "Defaults are not measured footprints or burned area"},
            {"target": "hfre_mw", "source": "Observed pixel power sums, satellite means and matched-window ratio", "type": "nullable MW", "rationale": "Power, not energy; missing measurements remain missing"},
        ],
    },
    {
        "target_table": "burning_calendar_cells",
        "anchor_source": "Included cell-window contributions plus explicit coverage declarations",
        "join_paths": ["Aggregate active metric by AOI/year/month", "Join same-month 2001..2020 baseline without recent-data fallback"],
        "fields": [
            {"target": "coverage_status", "source": "missing / records_only / complete", "type": "Coverage", "rationale": "Hotspot-only uploads cannot establish zero activity in absent months"},
            {"target": "z_robust", "source": "(value-median)/max(.7413*IQR,.5,0.18*median)", "type": "nullable heuristic", "rationale": "Explicit demo scale; rules require complete focus and >=5 complete reference months"},
            {"target": "empirical_percentile", "source": "100*(number below + .5*number equal)/n", "type": "nullable percent", "rationale": "Midrank within available same-month reference values"},
        ],
    },
    {
        "target_table": "fire_regime_summaries",
        "anchor_source": "calendar.summary_records (logical view); focus, phenology and decision are separate run objects",
        "join_paths": ["Use complete years for OLS/Theil-Sen trends", "Use 36-dekad baseline profile for shortest cyclic 90% activity season; flat or missing profiles undefined"],
        "fields": [
            {"target": "peak_year, trend_slope_per_decade", "source": "Complete annual active-metric totals only", "type": "nullable summary", "rationale": "Partial totals do not become complete-year trends"},
            {"target": "verdict (separate run field)", "source": "Deterministic versioned rules and Q0..Q8 evidence", "type": "Demo label", "rationale": "Receipt is unsigned consistency evidence, not source authenticity or validated hazard advice"},
        ],
    },
    {
        "target_table": "sensor_calibration_audit",
        "anchor_source": "Positive matched MODIS/VIIRS months, February 2012..December 2024",
        "join_paths": ["Pooled occupancy sum ratio needs >=3 months; otherwise assumed .58", "2012/2018 pre/post comparisons require three complete years per side"],
        "fields": [
            {"target": "bridge_r2, bridge_efficiency, bridge_rmse, bridge_mean_bias", "source": "Squared correlation and separate agreement diagnostics", "type": "nullable in-sample metrics", "rationale": "Correlation alone does not establish agreement or external accuracy"},
            {"target": "calibration_basis, era_diagnostics", "source": "Fitted or assumed bridge and descriptive sensor-era ratios", "type": "Provenance", "rationale": "Era ratios do not silently replace the pooled multiplier"},
        ],
    },
]
