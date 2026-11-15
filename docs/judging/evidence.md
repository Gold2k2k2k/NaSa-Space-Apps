# Judging evidence and claim limits

Assessment date: November 15, 2026, Asia/Saigon. The official [2025 judging
guide](https://spaceapps-v2-staging.s3.amazonaws.com/media/documents/Final_Space_Apps_2025_Judging_Guidelines_for_web.pdf)
is a dated reference for Impact, Creativity, Validity, Relevance and Presentation.
It is not a verified 2026 scoring model. No equal weights, total score, award
prediction or current format limit is inferred. The requested [current
guide](https://www.spaceappschallenge.org/resources/judging-awards-guide/) was
inaccessible during research. The team accepted this limited fallback.

| Criterion | Demonstrated evidence | Practical limit |
|---|---|---|
| Impact | Three-step land-manager review, periods to investigate, portable manager brief and six evidence formats | No actual manager study, outcome measure or operational impact established |
| Creativity | Original inspectable occupancy method, separate power fit, immutable source-preserving experiments and offline receipts | A prototype contribution; novelty relative to all existing tools has not been independently established |
| Validity | 37 pinned NASA sources; deterministic subset; fixed training and disjoint held-out assessment; negative FRP result retained; UNVERIFIABLE when coverage is unknown | Sensor agreement is not ground truth; no burned-area, causal or hazard validation |
| Relevance | Actual historical MODIS/VIIRS case, declared AOI, descriptive calendar/reference and reproducible sensor comparison | The exact current challenge/judging instructions require owner confirmation before submission |
| Presentation | Five views, guided entry, accessible brief, English narrative/slide outline, Vietnamese team notes and recorded browser proof | Seven slides is an internal proposal; public repository access and external submission remain pending |

## Measured model support

The [machine-readable report](results/model-evaluation.json) matches the applied
model in the [example receipt](../../output_examples/central_highlands_receipt.json).
Filters: nominal-or-high confidence, non-vegetation guard on. Train: 2013–2020;
held out: 2021–2024; available descriptive reference: 2001–2020.

| Quantity / period | Positive pairs | R² | RMSE | Mean bias | Efficiency |
|---|---:|---:|---:|---:|---:|
| Occupancy training | 73 months | 0.855524 | 5.669551 index | 0 | 0.837559 |
| Occupancy held out | 43 months | 0.841172 | 3.927599 index | −1.923674 | 0.786767 |
| Power training | 130 windows | 0.062509 | 25.363608 MW | 0 | −0.809132 |
| Power held out | 35 windows | 0.101068 | 45.475956 MW | 7.716203 | −5.058486 |

Applied κ: 0.1825270996234471; independently fitted FRP factor:
1.7570529471092355. Reported precision describes reproducibility, not physical
accuracy. Held-out power agreement is poor, with negative efficiency. Occupancy
has four unpaired recorded held-out months; power excludes 1,851 included
held-out windows without a positive pair. The guard excludes another 44 source
type windows. Missing/nonpositive observations are not manufactured as pairs.

February, March and January are the largest recorded reference medians, each
with 20 available same-month samples and **zero established complete samples**.
February 2024: 34.962541 HHE, reference median 45.189569, descriptive percentile
25, records-only coverage. The verified-hazard conclusion remains UNVERIFIABLE.

## Reproducibility and acceptance proof

- [Pinned manifest](../../app/data/central-highlands.manifest.json): exact original
  URLs, byte hashes/sizes, acquisition metadata, versions, clip and subset hash.
  `scripts/build_firms_case.py --cache-dir <originals> --check` compares the exact
  bundled bytes offline. `--download` explicitly obtains originals and rejects
  changed pinned bytes; analysis/import never requires network or this cache.
- [Regression tests](../../tests/test_judging_regressions.py): bounded broad
  longitude ingestion, nested invalid geometry types, display-independent median
  midrank including asymmetric ties, precision and empty references.
- [Model tests](../../tests/test_judging_calibration.py): known factors, held-out
  perturbations, windows across the boundary, sparse fallback and filter profiles.
- [Workflow tests](../../tests/test_judging_workflows.py): actual case HTTP/CLI,
  source-preserving experiments, tamper checks and extracted standard-library
  verification. [Brief tests](../../tests/test_judging_brief.py) retain evidence limits.
- [Browser tests](../../tests/test_browser_showcase.py): actual local HTTP,
  375/1440 px views, keyboard/reduced-motion checks, case/generated/upload flows,
  stale-response races, errors and all six downloads. This is automated browser
  checking, not a human accessibility certification or manager usability study.
- [Packet test](../../tests/test_judging_packet.py): deterministic source handoff,
  independently checked file hashes and exclusion of even tracked secrets/cache.

Final command results, revision/environment and screenshot identities are recorded
in [verification](verification.md). No public posting, visibility change or
deployment is part of this local package. Docker build remains unverified on a
Docker-enabled host. Independent field validation and real-manager testing are
next steps, not completed evidence.
