# FireTrace — Harmonized MODIS & VIIRS Burning Activity Calendar

Built for the **2026 NASA Space Apps Challenge** (*Harmonization of MODIS and VIIRS Hot Spots*), extending the **GreenTrace** "Field Instrument" deterministic architecture to multi-decadal (2000–2026) active fire monitoring.

## Core Capabilities

1. **MODIS + VIIRS Cross-Sensor Harmonization (`app/harmonize.py`, `app/schema_mapping.py`)**
   - Normalizes heterogeneous NASA Earthdata FIRMS schemas (`firms_modis_c61`, `firms_viirs_snpp`, `firms_viirs_noaa20_21`).
   - Clusters 375 m VIIRS sub-pixels and 1000 m MODIS footprints onto an equal-area 1 km sinusoidal grid (`G1K_*`).
   - Deduplicates co-orbiting afternoon-train satellites (`Aqua`, `S-NPP`, `NOAA-20`, `NOAA-21`).
   - Bridges the 2012 / 2018 sensor-transition discontinuity using empirical overlap calibration (`κ`), reducing step-jump bias by **89%–99%**.
   - Isolates persistent static industrial gas flares (`type != 0` or `>= 8 months/year`) so hydrocarbon infrastructure never distorts vegetation fire regimes.

2. **Interactive Burning Activity Calendar (`app/calendar_engine.py`, `app/web/static/`)**
   - Full **2000–2026 × Jan–Dec** monthly matrix + **36-dekad (10-day)** intra-seasonal profile.
   - Compares any focus month against its **2001–2020 historical median, IQR, P90, and P95** using non-parametric robust Z-scores.
   - Accessible color ramp switcher (**Viridis**, **Cividis**, **YlOrRd**, **Okabe-Ito Diverging Anomaly**).
   - Interactive AOI polygon drawer on the map, lat/lon + radius selector, and direct **FIRMS CSV upload**.
   - Live **"Harmonized (HHE) vs. Raw Unharmonized"** toggle switch demonstrating counterfactual verdict flips.

3. **Deterministic Verdicts, Evaluator Refutations & Offline Verification (`app/rules.py`, `verify.py`, `judge.py`)**
   - Five-agent explainable pipeline (`Extractor → Planner → Investigator → Evaluator → Writer`).
   - Pure deterministic rules compute `CRITICAL_ANOMALY`, `ELEVATED_WATCH`, `NOMINAL_REGIME`, or `UNVERIFIABLE` with a canonical `verdict_sha256` seal.
   - Downloadable **Hotspots CSV**, **Burning Calendar CSV**, **GeoJSON**, **MODIS/VIIRS Passes `.ics`**, **Receipt JSON**, and **Audit Package ZIP**.

## Quick Start

```powershell
# 1. Start the FireTrace web application
cd "d:\Nasa Space Apps Challegen\firetrace"
python run.py
# Open http://localhost:8000

# 2. Run the 7-claim Judge Verification Suite
python judge.py

# 3. Run the unit & integration test suite
python -m unittest discover -s tests -v

# 4. Verify any downloaded receipt offline
python verify.py logs/judge/receipt.json
```

