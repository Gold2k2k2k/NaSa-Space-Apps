# Reproducible analysis receipts

New analyses produce `firetrace-receipt-v2`. Download a receipt from the web
application or retrieve `/runs/{run_id}/receipt`, then verify it offline using
the matching FireTrace code:

```powershell
.\.venv\Scripts\python.exe verify.py receipt.json
```

Exit codes are `0` for `VALID`, `1` for inconsistent or modified evidence
(`TAMPERED`), and `2` for an unreadable or malformed receipt (`UNREADABLE`).

Version 2 includes the complete calendar, a normalized input summary and data
digest, all nine query rows, the rule source hash, and the displayed decision.
Verification checks the receipt checksum, required query identities and counts,
row hashes, query/evidence relationships, calendar digest and summary, and the
re-derived rules version, verdict, deciding rule, findings, and verdict seal.
JSON round-tripping preserves the canonical representation.
For v2 calendars, verification also requires exactly one cell for every year/month
in the declared window, matching analysis options and AOI. Focus measurements and
reference fields must match the selected cell. Annual totals, observed/complete
support, extrema, peak records and complete-year trends are checked against the
cells rather than trusted because their checksum is valid. Contradictory or
missing calendar evidence is rejected even after unsigned hashes are recomputed.
New v2 records also bind source/ingestion metadata, calculation identity,
reference time, modeled passes, lineage and any explicitly hypothetical metric.
New case records also bind the pinned source manifest/subset identities, fixed
calibration policy and matching training/held-out report. The verifier checks
their internal relationships and re-derives the manager brief from the same
snapshot. The manifest anchor belongs to the matching bundled code; it is not a
NASA signature. The complete reference history remains in calendar evidence.

The input summary counts sensors from normalized row values. A combined CSV
containing both `brightness` and `bright_ti4` columns does not turn VIIRS rows
into MODIS rows. Cluster counts include filtered thermal sources; the included
calendar-event count is a separate statistic.

The audit ZIP uses a fixed ZIP metadata epoch, stable member order, and fixed
permissions. A fixed run packaged with the same code and bundled documentation
produces identical archive bytes. Scientific reference times remain in the
analysis and exported data, rather than ZIP filesystem timestamps.
The ZIP includes complete exports, accepted source rows, full analysis inputs,
matching app sources, `verify.py`, method documentation and a raw-file SHA-256
manifest. Extract it and run `python -S -B verify.py receipt.json` without
third-party packages. Replaying the whole analysis additionally needs the
project's declared runtime dependencies. Source rows are not original CSV bytes.
CSV ingestion retains only accepted rows and reports rejections in metadata;
direct engine input can retain invalid rows, counted separately by normalization.
Actual-case ZIPs additionally contain `case_manifest.json` and
`model_evaluation.json`. The manager brief is retained in evidence and receipt.
Replay from `source_records.json` and `analysis_inputs.json` uses the included
full AOI/policy; it does not need to load the curated CSV again.

Version 1 receipts remain readable with a narrower verification scope. They did
not contain full calendar cells or independent input summaries, so those missing
relationships cannot be reconstructed from a v1 receipt alone. Verification
reports that limitation. Rules `.1` are frozen in `app/legacy_rules.py` for those
earlier records; new analyses use `.3`. Unknown rules or a mismatched versioned
rule source hash are rejected. Current rules are `2026-11-15.3`, with separate
preceding-month context bound in calendar, summary and Q7 even outside the selected
window. Earlier interim v2 `.2` receipts require their matching bundled verifier
and sources; this verifier accepts current `.3` and frozen legacy `.1` rules.
Preserve matching code with retained evidence.
Earlier v2 records without the new model, case manifest or manager brief retain
their existing narrower relationships; those fields cannot be reconstructed
from such a receipt alone. Optional extension checks apply when fields exist,
and the NASA archive source kind requires its pinned case manifest/model.

These are **unsigned consistency and reproducibility records**. Hashes do not
authenticate a NASA source, establish that input observations are true, or stop
someone from constructing an entirely new internally consistent receipt and
recomputing all hashes. Generated demonstration data and real uploaded
observations must remain distinguishable in the surrounding provenance.
