# 2026 NASA Space Apps Challenge Submission — FireTrace

- **Challenge:** Harmonization of MODIS and VIIRS Hot Spots
- **Project:** FireTrace — Harmonized MODIS & VIIRS Burning Activity Calendar & Deterministic Regime Investigator
- **Repository:** https://github.com/Gold2k2k2k/NaSa-Space-Apps

---

## 1. Executive Summary
Satellites have tracked active fires for over 26 years, but the historical record is split between **MODIS** (Terra & Aqua, 1000 m resolution, 2000–present) and **VIIRS** (Suomi NPP, NOAA-20, NOAA-21, 375 m resolution, 2012–present). Because a single 1 km² fire footprint triggers 5–8 sub-pixel VIIRS 375 m detections and afternoon-train satellites co-observe the same burn, naively summing raw FIRMS hotspots creates a false **+200% to +380% step jump in 2012**.

**FireTrace** harmonizes MODIS and VIIRS into a unified, sensor-agnostic unit — **Harmonized Hotspot Equivalents (HHE)** — and renders an interactive **2000–2026 Burning Activity Calendar** that empowers emergency responders, scientists, land managers, and firefighters to compare current burning activity against a 20-year historical median, separate wildfires from agricultural burns and industrial gas flares, and verify every finding offline via cryptographic receipts.

## 2. How FireTrace Meets Every Challenge Criterion

| Challenge Requirement | FireTrace Implementation |
|---|---|
| **MODIS & VIIRS Harmonization** | 4-stage pipeline in `app/harmonize.py`: schema normalization (`app/schema_mapping.py`), 1 km equal-area sinusoidal clustering (`G1K_*`), afternoon-train overpass deduplication, and 2012–2024 overlap calibration ($\kappa$, reducing step bias by 89%–99% with $R^2 > 0.96$). |
| **Burning Activity Calendar (2000–2026)** | Interactive **27-year × 12-month** heatmap matrix + **36-dekad (10-day)** intra-seasonal profile (`app/calendar_engine.py`), with live click-to-inspect and a physical **Harmonized vs. Raw** toggle switch. |
| **Historical Median & Anomaly Comparison** | Non-parametric 2001–2020 climatology computing monthly Median, Mean, IQR (Q25–Q75), P90, P95, relative anomaly ($\Delta\%$), and robust Z-score ($Z_{\text{robust}}$). |
| **Interactive Spatial Selection** | Draw custom polygons directly on the map, input Latitude/Longitude/Radius & Date Range, upload custom **NASA FIRMS CSV** archives, or explore 6 real-world benchmark fire regimes. |
| **Accessible Color Ramps** | Instant switcher between **Viridis**, **Cividis** (deuteranopia/protanopia safe), **YlOrRd**, and **Okabe-Ito Diverging Anomaly**, with automatic WCAG contrast foreground text. |
| **Downloadable CSV, GeoJSON, ICS & Receipt** | One-click exports for Harmonized Hotspots CSV, 27-Year Calendar Matrix CSV, Spatial GeoJSON, RFC 5545 `.ics` (upcoming Terra/Aqua/S-NPP/NOAA-20/21 passes + critical fire windows), and offline-verifiable `receipt.json` + Audit ZIP. |
