# Sources and credits

## NASA data and scientific context

- [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/),
  [country archive](https://firms.modaps.eosdis.nasa.gov/country/) and
  [yearly catalog](https://firms.modaps.eosdis.nasa.gov/data/country/yearly_summary_files.txt).
  The bundled [case manifest](app/data/central-highlands.manifest.json) records
  exact URLs, raw-file SHA-256/bytes, retrieval times, versions and the deterministic
  rectangle clip for 24 MODIS annual files (2001–2024) and 13 VIIRS S-NPP files
  (2012–2024). NASA data is credited separately from the project's code license.
  The subset preserves NASA values; it is not NASA endorsement or a certified
  complete observation record.
- [FIRMS FAQ and interpretation limits](https://www.earthdata.nasa.gov/data/tools/firms/faq).
  Hotspot location/FRP/confidence are observations with sampling limits, not
  physical incident counts, verified causes, burned area or predictions.
- [MODIS Collection 6.1 active-fire product](https://lpdaac.usgs.gov/products/mod14v061/),
  [VIIRS 375 m product](https://www.earthdata.nasa.gov/data/instruments/viirs)
  and the references in [scientific methods](docs/SCIENCE.md).
  The 1 km sinusoidal aggregation, confidence weights, temporal windows and
  fitted comparisons in FireTrace are original prototype choices, not an official
  NASA harmonization algorithm.

## Competition references

- [NASA Space Apps 2026 MODIS/VIIRS challenge](https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/).
  Current challenge search-index context was checked during research; direct
  page retrieval was intermittent. Confirm the complete current instructions
  before actual submission.
- [Official 2025 judging guidelines](https://spaceapps-v2-staging.s3.amazonaws.com/media/documents/Final_Space_Apps_2025_Judging_Guidelines_for_web.pdf):
  dated reference for the five criteria only. The [requested current guide](https://www.spaceappschallenge.org/resources/judging-awards-guide/)
  was inaccessible during research on November 15, 2026. No current scoring,
  timing or format requirement is inferred from the older document.
- [Space Apps legal terms](https://www.spaceappschallenge.org/legal/), checked
  during research with an August 7, 2026 update: original work, resource credits
  and an open license inform this local preparation. Publication and eligibility
  remain owner responsibilities before submission.

## Software, fonts and assistance

Original application core: FireTrace team and contributors. Dependencies are
declared in [requirements](requirements.txt) and [development requirements](requirements-dev.txt).
Their licenses remain their authors' licenses; see [third-party notices](THIRD-PARTY-NOTICES.md).
The locally bundled Geist/Geist Mono fonts are from Vercel and basement.studio
under the [included SIL OFL 1.1](app/web/static/fonts/OFL.txt).

See [AI assistance and generated-data disclosure](AI-DISCLOSURE.md). No live LLM
call is made by the application. Automated test results are software evidence,
not independent scientific validation or real-user research.
