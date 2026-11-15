# Calendar receipt consistency follow-up

A subsequent Standards/Spec review of `origin/main..6782d6e` found one P2 Spec
issue: updating the unsigned cell/envelope checksums allowed receipts with
missing, duplicated or contradictory calendar cells to verify as VALID.

The verifier now checks every displayed year/month exactly once, option/AOI
consistency, focus-cell correspondence, reference fields, annual totals/support,
extrema, peak records and complete-year trends. Required evidence cannot disappear
by substituting absence for an explicit nullable value. Malformed focus/summary
objects produce a controlled CLI error. Valid null measurements, cell reordering,
legacy v1 receipts and median scenarios retain their documented behavior.

The original forged February 2024 value, empty cells and duplicate cells are
rejected even when both hashes are refreshed. The failing regressions were observed before each repair. The new module now
contains 11 passing tests, including positive checks for valid nulls and cell
reordering:

```powershell
python -m unittest tests.test_receipt_calendar_consistency -v
python -m unittest discover -s tests -v
python judge.py
python smoke_test.py
```

**Final verification:** 177 tests PASS (347.618 seconds), judge 7/7, smoke 3/3
and HTTP benchmark 12/12. The [complete suite output](results/receipt-calendar-suite.txt)
includes all new regressions, existing median scenarios, exports and legacy
receipts. All four current reference receipts verify, generated examples remain
current, and `git diff --check` passes.

This changes verification relationships, not the underlying analysis or source
authenticity guarantees. No receipt regeneration was needed.
