# FireTrace local UI refresh

Implemented locally on November 15, 2026. At initial completion, no commit, push,
repository visibility change or deployment had been performed. The owner later
authorized publication on the separate `codex/firetrace-ui-review` branch for
team evaluation. Submission form and slide work remain deferred at the user's
request; deployment remains a separate step.

## Design basis

The user requested inspiration from the previous year's finalists and provided
the 2025 Global Winners directory. Three live winner sites were rendered in
Chrome: [SpaceGenes+](https://spacegenes-plus.framer.website/),
[Resonant Exoplanets](https://resonant-planet.vercel.app/) and
[AstroSweepers](https://astro-sweepers.vercel.app/home). The inspection concerns
the versions available on November 15, 2026, rather than archived 2025 versions.
The reference associations and access limitations are documented in
[DESIGN.md](../../DESIGN.md#2025-winner-references-for-the-local-ui-refresh).

Their clear purpose statements, prominent entry actions and distinct paths to
details inform the hierarchy. FireTrace retains its teal/ember palette, five
views, self-hosted fonts and zero-build stack. No reference-site artwork or code
was copied. No dependency, external asset request or scientific calculation was
added by the refresh.

## Resulting behavior

- The active location, purpose and result explanation share a compact overview
  with a featured NASA FIRMS case. The case action changes to an explicit reset
  action while NASA archive data is selected.
- The three-step guide is a short strip. Review periods navigates from Audit to
  the calendar and positions its heading below the sticky navigation.
- Four metric cards retain units, reference support and descriptive limits.
  Tablet layouts use two columns so numbers and words remain legible.
- The source warning stays visible. Full provenance expands through native
  details; accepted/rejected CSV counts remain visible before expansion.
- Generated presets remain explicitly generated. Actual FIRMS records retain
  unknown coverage, missing-not-zero semantics and UNVERIFIABLE results.

## Measured layout

Chrome screenshots used the same generated Amazon preset and loaded local
fonts. Values are CSS pixels from the top of the document to the calendar panel,
with source notes and region controls collapsed. They are layout measurements,
not usability-study results or estimates of judging performance.

| Viewport width | Before | After | Change |
| --- | ---: | ---: | ---: |
| 1440 | 707.1 | 680.9 | 26.2 px earlier |
| 375 | 1413.1 | 1066.4 | 346.7 px earlier; 24.5% reduction |

The full phone matrix remains below the first screen. Its guide link provides
direct access without shrinking the 44 px cells. Horizontal history, tables and
the narrowest navigation remain bounded scrolling regions.

## Visual audit

These are subjective implementation self-assessments, not an independent review
or WCAG conformance certification. Source locations identify the relevant
implementation, including checks made during the rendered inspection.

| Dimension | Score / 10 | Evidence and remaining limit |
| --- | ---: | --- |
| Color consistency | 9 | Semantic palette retained; generated, uploaded and archive sources have distinct labeled states in `app/web/static/app.css:39` |
| Typography | 8 | Larger location heading and tabular metrics; missing-value words fit narrow cards in `app/web/static/app.css:271` |
| Spacing | 9 | Shared token scale; overview, cards and short guide in `app/web/static/app.css:52` and `app/web/static/app.css:69` |
| Components | 9 | A clear featured entry/reset action and consistent metric surfaces in `app/web/static/index.html:40` and `app/web/static/app.css:121` |
| Responsiveness | 8 | All five views checked at 320, 375, 768 and 1440 px; two-column tablet metrics in `app/web/static/app.css:220`; wide evidence still needs bounded horizontal scrolling |
| Dark appearance | 9 | Existing opaque scientific surfaces and semantic tokens remain in `app/web/static/tokens.css`; no light theme is claimed |
| Motion | 8 | Short state transitions, no decorative scroll animation; reduced-motion support in `app/web/static/app.css:289` |
| Accessibility | 8 | Existing roving keyboard matrix, contrast checks and 44 px cells pass; calendar anchor respects the sticky header in `app/web/static/app.js:268`; no new manual screen-reader study |
| Information density | 8 | Short guide and expandable source details in `app/web/static/index.html:45` and `app/web/static/index.html:78`; dense evidence remains in its existing views |
| Polish | 8 | Current-case feedback, honest result explanation and visible CSV rejection counts in `app/web/static/js/views.js:16`; no remote assets or browser errors in the final visual check |

## Verification

177 existing regression tests passed across the two disjoint groups: 167 tests
outside `test_browser_showcase`, plus all 10 browser workflows. The upload
workflow was rerun after ensuring rejected-row counts remain visible and the
full notes can be opened. The guided real-case test now also checks navigation
from Audit to the calendar without covering its heading with the sticky header.

Browser checks cover generated and actual NASA sources, all five views,
keyboard exploration, scientific ramps and contrast, reduced motion, CSV upload
and drop, option and geometry preservation, hypothetical metric restoration,
late-response handling, errors/retry, the 12-case bench and all six downloads.

The final visual inspection also passed at 320/375/768/1440 px, including missing
metric values on small phones. Document width did not exceed viewport width,
metric text did not overflow its cards, and no remote requests or uncaught
browser errors occurred. Screenshot inspection caught and corrected narrow-phone
guide-label overlap. Chrome was the browser used; cross-browser and manual
assistive-technology validation were not added in this refresh.

`python scripts/build_design.py --check` and `git diff --check` pass. The design
token CSS and standalone interactive preview are synchronized with their source.

Local logs, reference renders, before/after screenshots and the reproducible
layout inspection script are under `.superpowers/ui-refresh/` (ignored local
artifacts). The running local preview is at `http://127.0.0.1:8075`.
