# NASA case reference-time correction

The branch review found that `run.py --case-study central-highlands
--reference-time 2024-06-01T00:00:00Z` exited 2 with `Case studies accept analysis
options only`. The CLI already accepted this documented flag, but the case
helper rejected it before the engine could validate or use it.

The helper now permits `reference_time` alongside analysis options and forwards
it through the existing engine path, including the automatic focus-month rerun.
The engine retains its timezone requirement, UTC normalization and 2000–2100
modeled-reference range. Unknown fields and geometry overrides remain rejected;
the NASA data, case defaults and calibration policy are unchanged.

## Regression coverage

The public CLI regression failed with the original code for both UTC and
`+07:00` input, then passed after the correction. It checks the normalized
reference in analysis JSON, modeled passes, stage timestamps, receipt and ZIP;
the receipt verifies as VALID and the ZIP passes its CRC check. It also checks
that the source identity and fitted model remain the same as the default case.

A second test covers malformed, timezone-free and out-of-range references:
controlled CLI exit 2, no traceback and no partial output files.

```powershell
python -B -m unittest tests.test_judging_workflows -v
python -B -m unittest discover -s tests -v
python -B scripts/generate_examples.py --check
python -B scripts/build_design.py --check
python -B scripts/build_schema_docs.py --check
```

`case_studies.py` is included in the calculation source digest, so the reference
receipts, real-case evidence and manager brief were regenerated. Their source
rows, scientific results and default reference remain unchanged; calculation
identity, run IDs and envelope hashes reflect the corrected source.

Earlier judging screenshots and replay logs identify their original historical
snapshot. The current reference receipt is in `output_examples/`.

## Verified result

The full suite passed: **179 tests**, 626.705 seconds, including both new CLI
regressions and all ten real-browser workflows. All four regenerated example
receipts verify as VALID with the standalone verifier. The example regeneration
check, design generation check, schema generation check and `git diff --check`
also passed. Logs and fresh browser captures are retained locally under
`.superpowers/p2-case-reference/`.
