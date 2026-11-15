# FireTrace design system

FireTrace is a scientific demonstration workspace. Its first job is to make the
source, comparison period, missing evidence and calculation assumptions easy to
see. The five views remain Calendar, Sensor Bridge, Audit & Receipt, Schemas and
Trap Bench. The user approved a dark teal/ember evolution of the existing app.

## Tokens and artifacts

`design-tokens.json` is the source for semantic colors, font families/type sizes,
4 px spacing, radii, elevation/shadows, motion, breakpoints and scientific ramps.
`python scripts/build_design.py` generates `app/web/static/tokens.css` and the
standalone `design-preview.html` from `design-preview.template.html`. Add `--check`
to detect stale artifacts. The shipped app needs no build step or external CDN.

The preview is interactive and dependency-free: change ramps, activity, density,
motion and control states. It contains invented values and uses installed font
fallbacks. The dashboard self-hosts the original Geist/Geist Mono font assets;
their SIL Open Font License remains in `app/web/static/fonts/OFL.txt`.

## Decisions and rationale

| Decision | Purpose |
| --- | --- |
| Dark teal background; pale teal signal; ember thermal accent | Continues the project's instrument identity while giving actions and measured series distinct roles |
| Glass only around navigation/selected controls | Grouped translucency establishes controls above content; heatmaps, charts, tables and receipt text stay opaque |
| Self-hosted Geist plus tabular Geist Mono | Clear interface hierarchy and aligned scientific numbers without a network font dependency |
| 4 px spacing scale; 10 px controls; 16 px panel corners | Gives related components a consistent rhythm while keeping actual cells and plotted geometry crisp |
| A compact header and collapsible region controls | Preserves space for the comparison instead of putting every input above it |
| Months as rows, years as columns | Makes the complete seasonal cycle scannable; mobile history scrolls inside its own region |
| 44 px calendar buttons and other controls | Supports touch and keyboard use; inline text links retain their natural text layout |
| Roving arrow-key calendar focus | One Tab stop enters the matrix; arrows/Home/End explore, Enter selects, and an inspector announces evidence |
| Persistent generated/uploaded source badge | Keeps provenance visible across all five views, including audit and schema navigation |
| Missing/partial coverage labels, gaps and distinct borders | Prevents an absent observation from looking like measured zero; numbers and labels carry meaning alongside color |
| Four scientific ramps with calculated foregrounds | Gives a color-vision alternative and explicit anomaly coloring while retaining legible cell numbers |
| Separate raw/HHE panels in Sensor Bridge | Avoids implying that the two different units share a comparable vertical scale |
| SVG descriptions and data-table alternatives | Supports reading exact values and using assistive technology without relying on hover or color |
| Bounded schedule region; complete downloads | Keeps a long modeled schedule usable without hiding rows or truncating exported evidence |
| Explicit source-preserving form updates | Period/confidence/audience changes retain uploaded records and full geometry; coordinate/geometry generation is labeled |
| Cancellation plus response revisions | Late requests cannot replace a newer selected result; failed work retains a clearly labeled previous snapshot |
| Location heading beside a featured NASA case | Establishes the active region and gives first-time visitors one clear route into observed data |
| Compact three-step review strip and a direct calendar anchor | Makes the manager workflow visible without repeating a large introduction above every view |
| Bordered metric cards and a wider heading scale | Separates the four measures while preserving their units, coverage and interpretation limits |
| Short source warning with expandable full notes | Keeps generated status, unknown coverage and ingestion counts visible; full provenance remains one click away |
| Human explanation beside the verdict | States what the result supports; complete rule and hash evidence stays in Audit & Receipt |

The requested Liquid Glass skill describes native iOS APIs. This Python/vanilla
web project uses a restrained CSS adaptation: one blurred navigation layer,
grouped translucent controls, subtle inset light, a solid fallback, and no nested
blur or decorative morphing. The app's selected appearance is deliberately dark;
it does not claim an unimplemented light theme. Reduced motion/transparency and
forced-color focus styles are provided.

## Color and accessibility contracts

Foreground selection uses linearized sRGB luminance, including the 0.04045
transfer threshold, then the actual contrast ratio. Opaque heatmap cells choose
the stronger of black/white; the mathematical lower bound is about 4.58:1.
Missing/undefined values use the neutral well and an explicit label rather than
a fabricated numeric color. Sequential color scales are labeled square-root;
the diverging scale states its clamped −3…+3 robust-Z domain.

Declared token ratios: body/surface **14.48:1**, secondary/raised **6.20:1**,
primary-control text/fill **10.57:1**, control boundary/well **4.15:1**, and
verdict text/background **7.51–8.60:1**. Dynamic heatmap colors are verified in
the browser. The targets follow the intent of W3C's
[contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
and [44 px target guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-enhanced.html).
These checks do not establish whole-application WCAG conformance or replace
manual assistive-technology evaluation.

## Rendered references

Read-only browser research on November 14–15, 2026 inspected:

- [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/map/): source/date context,
  layer grouping and clearly stated limits near spatial evidence.
- [Global Nature Watch global dashboard](https://globalnaturewatch.org/dashboards/global/):
  location-first hierarchy, concise summary, linked charts and downloadable data.
- [NASA Worldview](https://worldview.earthdata.nasa.gov/): persistent temporal
  context, grouped instrument controls and explicit layer provenance.

EFFIS Version 1 was decommissioned; its Version 2 link rendered blank in this
research session and supplied no usable design evidence. Browser MCP desktop
access was denied, so a fresh headless Chrome session captured the references.
No third-party interface code, map imagery or assets were copied into FireTrace.

### 2025 winner references for the local UI refresh

On November 15, 2026, headless Chrome rendered the live project sites below,
using the user's [2025 Global Winners directory](https://www.spaceappschallenge.org/2025/awards/global-winners/)
and [NASA's winner announcement](https://www.nasa.gov/learning-resources/stem-engagement-at-nasa/nasa-announces-2025-international-space-apps-challenge-global-winners/)
to establish the reference set. These are the versions available on the inspection
date, not archived screenshots of their 2025 submissions. The directory returned
HTTP 502 during this session; NASA's announcement confirmed the winner names.

| Rendered reference | Observed interface pattern | FireTrace adaptation |
| --- | --- | --- |
| [SpaceGenes+](https://spacegenes-plus.framer.website/) | A plain-language purpose, a prominent Explore Dashboard action, and an immediate dashboard preview | A concise purpose above the active region's evidence and a clear real-data entry |
| [Resonant Exoplanets](https://resonant-planet.vercel.app/) | Strong heading hierarchy, a primary Launch Explorer action and separate research/method links | Larger location heading; primary NASA case action; detailed methods kept in their existing views |
| [AstroSweepers](https://astro-sweepers.vercel.app/home) | A single central message, one primary action and restrained navigation | Consistent navigation and a short three-step route through the scientific workspace |

Only interface hierarchy and interaction ideas inform the refresh. The sites'
scientific and performance claims are not evidence for FireTrace. SkySense's
linked demo domain was parked, so it supplied no usable project UI reference.
No external artwork, code, fonts or runtime dependencies were added. The refresh
retains the existing five views, semantic palette, original data model and source
preservation rules. It is local work; publishing and deployment are separate.

## Verification and visual audit

The recovered Antigravity survey scored the prior interface 49.5/100. That is a
historical survey result, not a fresh rendered score. A separate baseline browser
capture found 556 px document width at a 375 px viewport, a 292 px mobile header,
and no keyboard calendar cells. Early rebuilt captures show a 375 px document,
113 px header, 324 native cell buttons and a roving keyboard entry, with no
uncaught errors or failed requests on the initial calendar load.

Final browser evidence covers all five views at 375/1440 px, real HTTP workflows,
ramps, keyboard focus, reduced motion, source preservation, races, errors and
downloads. The independent final audit must score color, typography, spacing,
components, responsiveness, dark appearance, motion, accessibility, density and
polish, with concrete file/line findings. Its report belongs in `docs/verification/`
after the implementation and required fixes are verified.

The November 15 local refresh has a separate [rendered audit and verification
record](docs/verification/2026-11-15-local-ui-refresh.md). It distinguishes the
current before/after measurements from the historical Antigravity survey.
