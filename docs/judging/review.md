# Independent final review and resolutions

One fresh read-only reviewer examined `b9a8815..5b59b13`, including worktree
status, against both Standards and the approved Spec. No other reviewer was
dispatched for this delta. The reviewer inspected the actual subset and rendered
evidence. Its assessment was **with fixes**, with three actionable issues:

| Axis / priority | Finding | Resolution and regression |
|---|---|---|
| Standards / P1 | Git `core.autocrlf=true` could convert the pinned CSV/manifest to CRLF and break case loading | `.gitattributes` pins LF for both; a temporary real Git checkout exercises loading under autocrlf; the handoff retains the attributes file |
| Standards / P2 | Rehashed receipts could contain evaluation pair counts contradicting their agreement/model support | Verifier checks all training/held-out occupancy/power pairs against `agreement.sample_count`, and training pairs against the fitted model |
| Spec / P2 | Sparse inputs using FRP identity assumptions were labeled independently fitted | Assessment wording follows the actual occupancy/FRP basis and displays positive training support; real-server upload/browser regression checks the assumption label |

All three were reproduced as failing tests before the repairs. The packet
regression also first failed when `.gitattributes` was excluded. The complete
suite was rerun after this single fix pass: **166 tests PASS** (361.602 s), with results retained in
[verification](verification.md). No second review is substituted for those
regressions and the full suite. No minor findings were deferred.

The reviewer independently corroborated the bounded longitude/nested-type/
fixed-reference repairs, boundary partitioning and ordinary source-switch revision
checks; subset hash, all 16,258 coordinates and sensor totals; six screenshot
hashes; records-only/UNVERIFIABLE wording; and the negative held-out FRP result.

## Scope rulings

The reviewer declined to judge these external matters. Each remains explicitly
limited, rather than silently treated as satisfied:

- **Current competition eligibility:** keep the 2025 rubric as a dated reference
  and 2026 rules unverified. Cost if assumed eligible: a submission could fail
  current requirements; the owner must check them before submitting.
- **Publication:** retain a local source handoff; do not claim the private repo is
  publicly accessible. Cost if omitted later: judges may be unable to open links.
- **Deployment:** preserve the user's deferred deployment decision. Cost: no
  hosted service is supplied by this package.
- **Operational fire detection:** keep the historical prototype scope, modeled
  passes and no operational warning claims. Cost if misused: evidence cannot
  support live operational decisions.
- **Field validity:** retain UNVERIFIABLE with unknown coverage and no ground
  truth claim. Cost: the current model cannot establish a verified hazard.
- **Actual manager usability:** automated browser proof remains separate from a
  real-manager study. Cost: usability and management impact remain unmeasured.

Other execution decisions are listed in [verification](verification.md): preserve
the selected feature checkout, native Windows execution, fixed-reference precision
and serialized-JSON replay. These rulings do not authorize public posting,
repository-access changes or deployment.

## Subsequent full-branch review

The later `origin/main..6782d6e` review reported zero Standards findings and one
P2 Spec finding concerning missing/contradictory calendar cells in rehashed
receipts. The [calendar consistency follow-up](receipt-calendar-fix.md) records
its targeted repair and verification separately from the three earlier findings.
