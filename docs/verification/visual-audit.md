# Independent visual audit — November 15, 2026

**Score: 88/100. No remaining important visual fixes.**

A fresh, read-only evaluator inspected all five views at 1440/375 px and full
Calendar, Bridge and Audit captures, plus the design rationale, tokens and
relevant source. The evaluator made no implementation changes. The score is a
visual judgment, not a measurement of scientific validity or WCAG conformance.

| Dimension | Score | Evidence |
| --- | --- | --- |
| Color consistency | 9 | Teal actions, ember thermal evidence and verdict colors have distinct roles; scientific ramps are purposeful |
| Typography hierarchy | 9 | Clear titles, headings, captions and tabular metrics; mobile seasonal labels remain separated |
| Spacing rhythm | 9 | Consistent padding/control spacing and aligned experiment-card actions |
| Component consistency | 9 | Coherent navigation, badges, disclosures, buttons and tables across the five views |
| Responsive behavior | 9 | Five mobile navigation items fit; Bridge retains the full timeline and both transitions; overflowing tables advertise scrolling |
| Dark appearance | 9 | Complete surface hierarchy with opaque scientific charts/tables |
| Animation | 8 | Restrained control transitions and reduced-motion source rules; motion was not independently exercised by this evaluator |
| Accessibility | 8 | Numbers, labels, dashes/borders and dashed series supplement color; native controls/focus exist; no independent assistive-technology test |
| Information density | 9 | Progressive disclosure, separate units, KPI hierarchy and a bounded schedule organize substantial evidence |
| Polish | 9 | Explicit ready/completed states, intact verdicts/hashes, aligned actions and readable chart labels |

## Findings corrected and visually rechecked

- Mobile verdict words broke inside narrow table columns. Table badges now keep
  their labels intact (`app/web/static/app.css:148`).
- Mobile receipt hashes expanded into many short lines and dominated the page.
  Full digests now remain on one line inside a focusable scrolling region
  (`app/web/static/app.css:150`).
- Some horizontal evidence was clipped without a visible cue. Scroll hints now
  accompany overflowing regions (`app/web/static/app.js:111`); Bridge instead
  fits the entire timeline with fewer mobile year labels
  (`app/web/static/js/charts.js:184`).
- Optional refinements aligned experiment-card actions and reduced mobile month
  label density (`app/web/static/app.css:123`, `app/web/static/js/charts.js:155`).
- The remaining optional hint-copy refinement was applied: tables refer to
  columns and charts refer to timelines, instead of a generic combined phrase.

## Pattern review and limits

No material generic-design pattern was flagged. Gradients encode data, glass is
restrained around controls/navigation, and the interface prioritizes domain
evidence over decorative hero content. Geist and monospace metrics suit the
instrument character.

This evaluator inspected rendered images and source. Runtime workflow,
contrast-ratio and keyboard claims rely on the separate actual-HTTP browser
suite. The known schema/documentation semantic cleanup was excluded from this
visual assessment and is tracked separately before final delivery.
