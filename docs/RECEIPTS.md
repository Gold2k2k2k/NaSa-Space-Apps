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
New v2 records also bind source/ingestion metadata, calculation identity,
reference time, modeled passes, lineage and any explicitly hypothetical metric.

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
project's declared runtime dependencies. Source rows are not original CSV bytes
and do not include rejected rows; ingestion metadata reports those rejections.

Version 1 receipts remain readable with a narrower verification scope. They did
not contain full calendar cells or independent input summaries, so those missing
relationships cannot be reconstructed from a v1 receipt alone. Verification
reports that limitation. Rules `.1` are frozen in `app/legacy_rules.py` for those
earlier records; new analyses use `.2`. Unknown rules or a mismatched versioned
rule source hash are rejected. Preserve the matching code with retained evidence.

These are **unsigned consistency and reproducibility records**. Hashes do not
authenticate a NASA source, establish that input observations are true, or stop
someone from constructing an entirely new internally consistent receipt and
recomputing all hashes. Generated demonstration data and real uploaded
observations must remain distinguishable in the surrounding provenance.
