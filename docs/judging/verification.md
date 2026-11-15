# Local verification record

November 15, 2026, Asia/Saigon. Application and review-fix checkpoint: `c7d0b40` on
`codex/firetrace-upgrade`; this record's commit also contains the presentation,
packaging and regenerated examples tested in the same working tree. No merge,
push, visibility change or deployment was performed for this judging package.

Environment: Windows 10.0.26300, Python 3.11.5 (64-bit), FastAPI 0.162.7,
Pydantic 2.14.3, Playwright 1.65.2, Chrome 157.0.8103.78. A fresh local virtual
environment used `requirements-dev.txt`. Linux/macOS and a Docker container
build were not exercised in this verification.

| Check | Actual result | Retained evidence |
|---|---|---|
| `python -m unittest discover -s tests -v` | **166 tests PASS**, 361.602 s | [Complete output](results/unittest.txt) |
| `python judge.py` | **7/7 PASS** | [Judge output](results/judge.txt) |
| `python smoke_test.py` | **3/3 PASS**, HTTP trap bench **12/12** | [Smoke output](results/smoke.txt) |
| `python -m pip check` | No broken requirements | [Environment metadata](results/environment.json) |
| `python scripts/build_design.py --check` | PASS | Committed tokens and preview match generator |
| `python scripts/build_schema_docs.py --check` | PASS | Schema reference matches API declarations |
| `python scripts/generate_examples.py --check` | PASS | Three generated examples plus real case/report/brief current |
| NASA subset rebuild `--check` | Byte equality, **16,258 rows** | [Pinned manifest](../../app/data/central-highlands.manifest.json) |
| All four current example receipts | **VALID**, nine queries each | [Examples](../../output_examples/) |
| Extracted audit replay | Same run ID and **identical serialized receipt JSON** | [Replay output](results/replay.txt) |
| Audit member integrity / determinism | **43 members**, all raw-file hashes correct; repeat package bytes equal | [Replay output](results/replay.txt) |
| Local handoff builder | Literal-byte fixture PASS; deterministic ZIP and tracked secret/cache exclusions | `tests/test_judging_packet.py` and full-suite log |
| `git diff --check` | PASS | No whitespace errors |

The exact replay run is `ft-7b337445cf811a976a93b468`. Its archive hash in the
replay log identifies that documentation/source snapshot; changing bundled
documentation changes an audit ZIP's bytes without changing the analytical
result. Current source/model identities are in the example receipt.

## Rendered browser proof

Automated real-server checks cover all five views at 375 and 1440 px, calendar
keyboard navigation, reduced motion, color ramps, actual/generated/uploaded
sources, immutable scenarios, filters, personas, error handling, latest-request
races and all six download formats. No unexpected browser exception, remote
asset request or document-width overflow remained in the passing run.

- [Manager brief, desktop](images/manager-brief-1440.png) and
  [phone](images/manager-brief-375.png).
- [Applied model/held-out assessment, desktop](images/model-assessment-1440.png)
  and [phone](images/model-assessment-375.png).
- [Calendar context, desktop](images/calendar-1440.png) and
  [phone](images/calendar-375.png).

Panel captures hide the fixed navigation/skip link only during the screenshot
to avoid covering clipped content. Product CSS is unchanged by that capture.
These are recorded demonstrations of this snapshot, not live imagery or a human
accessibility/usability study. File identities are in [screenshot metadata](results/screenshots.json).

## Acceptance mapping

| Approved requirement | Implementation / proof |
|---|---|
| Three reproduced defects | `test_judging_regressions.py`: bounded wrapped geometry/CSV, malformed nested types → 422, full-reference median midrank including fractional ties and empty history |
| Actual reproducible NASA case | `build_firms_case.py`, pinned CSV/manifest, `test_judging_case_data.py`, deterministic original-file rebuild |
| Disjoint training/assessment of both factors | `calibration.py`, partitioned `harmonize.py`, known-ratio/future-perturbation/year-boundary tests, matching measured model report |
| Honest missing coverage and scientific meaning | No complete periods on case; UNVERIFIABLE through experiments; explicit HHE/FRP/cause/boundary limits in brief, UI and submission |
| Immutable case workflow and portable proof | Case API/CLI, full AOI/source/policy retention, tamper tests, six browser downloads, extracted verification and exact JSON replay |
| Manager task within five views | Separate NASA entry, three steps, source labels, same-snapshot brief, receipt/ZIP links, mobile/keyboard browser proof |
| Judging/presentation/release preparation | English submission and slides, Vietnamese notes, dated rubric evidence matrix, source/AI/font/dependency credits, Apache-2.0 and deterministic local ZIP builder |
| Independent final review | [One fresh read-only review](review.md) identified three issues; all were reproduced and fixed, then the complete 166-test suite passed. No minor findings deferred |

## Execution decisions and practical limits

- Continue in the user-selected feature checkout and use PowerShell/Python
  equivalents of POSIX task helpers. The consequence is Windows-only execution
  evidence; cross-platform verification remains separate.
- Check empirical midrank against the unrounded fixed reference, while respecting
  six-decimal public precision. This preserves asymmetric ties rather than
  assigning a fabricated 50th percentile.
- Replay equality is equality of serialized JSON; Python tuples in rule references
  serialize to arrays. The initial in-memory tuple/list assertion was corrected;
  no analytical or evidence mismatch remained.
- Keep the branch and local handoff in place under the approved scope. Public
  accessibility, exact current submission rules, actual manager testing,
  independent field validation and deployment remain external follow-up.

The 2025 rubric is a labeled fallback; see [criterion evidence and limits](evidence.md).
