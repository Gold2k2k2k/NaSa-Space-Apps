# Semantic Schema Mapping Manifesto: MODIS & VIIRS Harmonization

This manifesto documents the exact source-to-target schema mapping across the three heterogeneous NASA Earthdata FIRMS streams into the four unified analytical tables used by **FireTrace**.

## Source Schemas

1. **`firms_modis_c61`** (Terra & Aqua MODIS Collection 6.1, 2000–present, 1000 m nadir)
   - `{latitude, longitude, brightness, scan, track, acq_date, acq_time, satellite, instrument, confidence: int(0..100), version, bright_t31, frp, daynight, type}`
2. **`firms_viirs_snpp`** (VIIRS Suomi NPP 375 m, 2012–present)
   - `{latitude, longitude, bright_ti4, scan, track, acq_date, acq_time, satellite, instrument, confidence: 'l'|'n'|'h', version, bright_ti5, frp, daynight, type}`
3. **`firms_viirs_noaa20_21`** (VIIRS NOAA-20 / JPSS-1 2018+ & NOAA-21 / JPSS-2 2023+, 375 m)
   - `{latitude, longitude, bright_ti4, scan, track, acq_date, acq_time, satellite, instrument, confidence: 'l'|'n'|'h'|'low'|'nominal'|'high', version, bright_ti5, frp, daynight, type}`

---

## Target Table 1: `harmonized_hotspots`
- **Anchor Source**: Union of `firms_modis_c61`, `firms_viirs_snpp`, `firms_viirs_noaa20_21` clustered onto `(cell_id, acq_date, daynight)`.

| Target Field | Source Field / Logic | Mapping Type | Rationale |
| :--- | :--- | :--- | :--- |
| `hotspot_id` | `SHA256(cell_id, acq_date, daynight)[:12]` | Derived | Deterministic unique ID per 1 km cell-pass |
| `cell_id` | `G1K_{floor(lat*100)}_{floor(lon*100*cos(lat))}` | Derived | Equal-area ~1 km grid eliminates 1 km vs 375 m pixel mismatch |
| `lat`, `lon` | FRP-weighted `AVG(latitude)`, `AVG(longitude)` | Aggregated | Preserves thermal centroid inside each 1 km cell |
| `acq_date`, `year`, `month`, `dekad` | ISO-8601 `acq_date` -> `Y`, `M`, `dekad (1..36)` | Derived | Standardizes monthly and 10-day calendar axes |
| `daynight` | `UPPER(TRIM(daynight))` | Derived | Separates diurnal crop burns from nighttime wildfires |
| `sensor_family` | `MODIS \| VIIRS \| HARMONIZED_BOTH` | Derived | Tracks sensor lineage while downstream metrics are sensor-agnostic |
| `mir_bt_k` | `COALESCE(bright_ti4, brightness)` | Synonym Resolution | Maps MODIS Ch 21/22 and VIIRS I4 mid-infrared brightness |
| `tir_bt_k` | `COALESCE(bright_ti5, bright_t31)` | Synonym Resolution | Maps MODIS Ch 31 and VIIRS I5 thermal infrared brightness |
| `confidence_class`, `confidence_weight` | MODIS `0..100` & VIIRS `l/n/h` -> `{low:0.45, nominal:0.80, high:1.00}` | Derived | Resolves numeric vs categorical confidence mismatch |
| `effective_area_km2` | `scan * track` | Derived | Captures off-nadir bow-tie footprint growth |
| `raw_detections` | `COUNT(*)` | Aggregated | Audits raw count inflation prior to harmonization |
| `overpass_dedup_factor` | `1.0 / COUNT(DISTINCT afternoon_satellites)` | Derived | Deduplicates Aqua + S-NPP + NOAA-20 + NOAA-21 co-detections |
| `hhe` | Harmonized Hotspot Equivalent | Derived | Sensor-agnostic burning unit calibrated across 2012–2024 overlap |
| `hfre_mw` | Calibrated Fire Radiative Power (MW) | Derived | Cross-sensor harmonized radiative fire energy |
| `fire_category` | `WILDFIRE \| AGRICULTURAL_BURN \| STATIC_FLARE` | Derived | Separates static industrial flares (`type!=0` or `>=8 mo/yr`) |

---

## Target Table 2: `burning_calendar_cells`
- **Anchor Source**: `harmonized_hotspots` aggregated by `(aoi_id, year, month)`, joined against 2001–2020 baseline climatology.

## Target Table 3: `fire_regime_summaries`
- **Anchor Source**: `burning_calendar_cells` aggregated across user AOI & date range, scored deterministically by `app/rules.py`.

## Target Table 4: `sensor_calibration_audit`
- **Anchor Source**: 2012–2025 overlap detections quantifying `raw_viirs_to_modis_ratio`, `calibrated_kappa`, `overpass_duplicates_removed`, `raw_step_jump_2012_pct`, `harmonized_step_diff_2012_pct`, `bias_reduction_pct`, and `bridge_r2`.

