# Accessibility Audit -- ovnis-pr Dashboard

Audit date: 2026-08-24
Scope: `dashboard/` (React/Vite SPA), the single real route (`/`) and its
in-page states -- the Cases/Statistics/Candidates tabs and the Case Detail
sheet. This is a follow-up pass to `docs/GUI_AUDIT.md` (controls inventory,
merged), focused specifically on accessibility (axe/WCAG-mapped rule
violations, touch-target sizing, keyboard focus visibility, layout overflow)
and on cataloging how this app actually sources its UI from the shared
`@pr-federation/react` design-system package versus its local shadcn/ui
primitives (`docs/design-system-usage.json`, generated alongside this audit).

## Overview

OVNIS (`ovnis-pr`) is the PRII federation's historical UAP/anomalous-event
case-corpus producer. Its dashboard is an internal diagnostic tool (per the
repo README and ADR 0001, Phase 2) rather than the federation's end-user
product surface -- one route, ~470 bundled sample cases, no auth, read-only
backend. That scope explains why this audit's findings below are worth fixing
but are not "public-facing outage" severity.

**Tech stack relevant to this audit:** React 19 + Vite 8, Radix UI primitives
wrapped by a near-full local shadcn/ui set (`new-york` style, 49 primitives
under `dashboard/src/components/ui/`), Tailwind CSS 4, MapLibre GL for the
case map, Recharts for the two Statistics charts, and `@pr-federation/react`
pinned to `0.3.0` for the shared federation design tokens/components. See
`docs/design-system-usage.json` for the full design-system-sourcing map; the
short version is that this app renders almost everything through its own
local shadcn primitives or bespoke markup, and touches the federation
package for exactly one thing live (`FederationEmptyState`).

## Method

**Live environment.** `cd dashboard && npm install` (already present from a
prior session), backend started with `uvicorn server.backend.main:app --host
127.0.0.1 --port 8105`, frontend with `VITE_API_BASE=http://127.0.0.1:8105
npx vite --port 5305 --strictPort --host 127.0.0.1`. The backend's hardcoded
CORS allow-list (`:5173` only) was temporarily patched in
`server/backend/main.py` to also permit `:5305` for the duration of this
audit, and reverted before the final commit -- `git status` / `git diff
origin/main -- server/backend/main.py` confirm the file is byte-identical to
`main` again. Page title (`OVNIS · Ovnis-PR UAP Registry`) confirmed the app
rendered before scanning began.

**Tooling.** The shared, pre-provisioned a11y runner at `/home/user/.a11y-runner`
(pinned Playwright 1.62.1, `@axe-core/playwright` 4.12.1, explicit Chromium
at `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`) was used, but its
generic single-route spec (`tests/federation-smoke.spec.js`) only exercises
one static URL and can't drive this app's in-page tab/sheet states. **A
custom, throwaway Node script was written for this audit** (using the
runner's own installed `playwright` + `@axe-core/playwright` packages, no new
dependencies installed, no `playwright install` run, no changes to the
runner's `playwright.config.js`/`package.json`/`node_modules`) that: loads
`http://127.0.0.1:5305/`, waits for `networkidle` + an 800ms settle (per the
runner's documented SPA-hydration-race fix), then for each of the two
required viewports (390x844, 1280x800) walks four states -- the default Cases
tab, the Case Detail sheet (opened by clicking the first case row), the
Statistics tab, and the Candidates tab -- running, **sequentially** (not
concurrently, to avoid the keyboard/focus check's DOM mutation racing axe's
snapshot): an axe scan, a `button:visible` touch-target sweep (44px minimum,
width and height), a `document.documentElement.scrollWidth >
clientWidth` horizontal-overflow check, and a keyboard-focus-outline check
(blur current focus, press Tab, inspect the newly-focused element's computed
outline/box-shadow). The script also captured the two Case Detail sheet
screenshots this audit adds. It was deleted after the run --
`/home/user/.a11y-runner` contains no files this audit added.

One environment adaptation: the map panel fetches OpenStreetMap raster tiles
over the open internet, which this sandbox cannot reach (`docs/GUI_AUDIT.md`
notes the same limitation) -- failed/retrying tile requests never let
Playwright's `networkidle` detector settle, so the script blocks
`*.tile.openstreetmap.org` requests via `page.route(...).abort()` before
navigating. This has no effect on any in-page content under test (tabs, grid,
sheet, charts) and does not touch application code.

**Documented scope limitations, explicitly, not silently:**
- **Two viewports only** (390x844 mobile, 1280x800 desktop), matching the
  task's fixed pair -- not a responsive breakpoint sweep.
- **Single theme only.** This app hardcodes a dark theme
  (`document.documentElement.dataset.theme = 'dark'` in `main.jsx`) with no
  toggle and no separate light token set in `index.css` -- there is no light
  theme to capture. The six screenshots reused from the prior session's
  attempt are filenamed `...-light.png`; that suffix is a naming artifact of
  a generic capture pass that assumed a togglable theme, **not** evidence
  that a distinct light theme exists or was captured. See
  `docs/design-system-usage.json` `themeSupport` for the full note.
- **Four in-page states per viewport** (Cases tab, Case Detail sheet,
  Statistics tab, Candidates tab) -- not every filter/search permutation
  inside CaseGrid, and not the Select dropdowns' own open-menu state.
- **Automated checks only** (axe rule engine + the three scripted checks
  above) -- no manual screen-reader pass (e.g. VoiceOver/NVDA) was performed.
- Map interactions (drag/scroll-to-zoom, clicking a map dot to open Case
  Detail) were not exercised by this script; `docs/GUI_AUDIT.md` already
  covers those live, and the Case Detail sheet was opened via a table-row
  click instead (equivalent resulting state, different trigger).

## Results by tab/state

Both viewports showed the same violation set per state except where noted;
"Overflow" is `document.documentElement.scrollWidth > clientWidth`.

| State | 1280x800 axe (critical/serious) | 390x844 axe (critical/serious) | Touch-target fails | Overflow (1280) | Overflow (390) | Focus outline visible |
|---|---|---|---|---|---|---|
| Cases tab (default) | `button-name` (critical) x2, `link-in-text-block` (serious), `scrollable-region-focusable` (serious) | `button-name` (critical) x2, `scrollable-region-focusable` (serious) | 7 both viewports | No | **Yes** | Yes |
| Case Detail sheet | `aria-hidden-focus` (serious) | `aria-hidden-focus` (serious) | 8 both viewports | No | **Yes** | Yes |
| Statistics tab | `link-in-text-block` (serious) | none | 5 both viewports | No | **Yes** | Yes |
| Candidates tab | `link-in-text-block` (serious) | none | 5 both viewports | No | **Yes** | Yes |

The `link-in-text-block` violation appears only at the desktop viewport --
see Finding 3 below for why (the map, which is where the offending link
lives, effectively disappears on mobile for an unrelated, worse reason).

Full raw output (all four viewport x state axe violation lists in full, with
selectors) was captured during this session; the summary above and the
Findings below are its complete critical/serious content -- nothing was
trimmed for brevity beyond the touch-target/overflow tabulation.

## Findings (prioritized)

> **Status update (2026-10-25):** Findings 1 and 2 were addressed after this
> audit. Below 860px the dashboard now uses a mobile shell (header, bottom
> navigation, card list, bottom-sheet case detail) instead of the fixed 440px
> pane, and the period / tier selects carry accessible names. The text below is
> the original 2026-08-24 record and is left as written. See
> `dashboard/README.md` ("Layout: desktop and mobile"); verified at 390x844,
> 430x932 and 844x390 by `dashboard/tests/gui-parity-mobile.spec.mjs`.

### 1. [High] Mobile viewport is not responsive -- the sidebar overflows the screen and the map becomes fully inaccessible

At 390px width, the right-hand tab panel (`<aside className="w-[440px]
shrink-0" ...>` in `dashboard/src/pages/Dashboard.jsx`) does not shrink: it
renders at its fixed 440px regardless of viewport. Measured live at
390x844: the `<aside>` occupies the full 441px, and the map's flex container
(`flex-1 min-w-0`) is squeezed to **0px width** -- `document.documentElement`
measured `scrollWidth: 449` vs `clientWidth: 390` (59px of forced horizontal
overflow). Consequences, all confirmed live:
- The map -- including MapLibre's zoom controls and the click-a-dot-to-open-
  Case-Detail interaction documented in `docs/GUI_AUDIT.md` -- is entirely
  invisible and unusable at this viewport, not just visually cramped.
- This is the root cause of the `horizontalOverflow: true` result on **every
  one of the four scripted states** at 390x844 (see table above); it is one
  layout defect, not four independent ones.
- It also explains why `link-in-text-block` (Finding 3) only fires at the
  desktop viewport: the MapLibre attribution link this rule flags lives
  inside the collapsed 0px-wide map container on mobile, so axe's
  visibility heuristics treat it differently there -- a side effect of the
  same root cause, not a separate mitigation.

This is a genuine mobile-usability gap (this dashboard is explicitly an
operator diagnostic tool per its README, but "operator on a phone" is a
plausible real use case) and the single highest-impact finding in this pass.

### 2. [Medium] `button-name` (critical, axe rule) on the decade/tier filter selects -- axe cannot compute an accessible name, though the text is visibly rendered

`CaseGrid.jsx`'s two Radix `Select` filter triggers (`h-7 w-[100px]` /
`h-7 w-[90px]`, labeled "All decades" / "All tiers") render as
`<button role="combobox">` containing `<span style="pointer-events:
none;">All decades</span>`. axe's `button-name` rule (critical impact, WCAG
4.1.2) fails both with `button-has-visible-text: false` -- i.e. it does not
count that span's text as an accessible name -- even though the text is
genuinely on screen (confirmed both visually and via this audit's own
touch-target sweep, which reads the same text via `.innerText()`
successfully). The shared shadcn `SelectTrigger` wrapper applies
`[&>span]:line-clamp-1` (`-webkit-line-clamp: 1; overflow: hidden`) to that
span; axe-core has a known history of treating `-webkit-line-clamp` +
`overflow: hidden` truncation as "possibly not visible to screen readers"
rather than "clipped-but-present" in some versions/rules. That mechanism is
plausible here but was not independently confirmed with a screen reader in
this pass (see Scope limitations) -- **recorded as a real, reproducible axe
finding, flagged for a manual screen-reader check** to determine whether it
is a true accessible-name gap or an axe/line-clamp interaction artifact,
rather than asserting a root cause not directly verified.

### 3. [Medium] `link-in-text-block` (serious, axe rule) -- MapLibre's "MapLibre" attribution link

Traced to the always-present MapLibre attribution control (bottom of the map
panel), specifically its `<a href="https://maplibre.org/">MapLibre</a>` link
-- rendered as plain text with no non-color distinguishing style (underline,
etc.), so axe flags it as not distinguishable from surrounding text without
relying on color (WCAG 1.4.1). This is third-party MapLibre GL JS chrome, not
app-authored markup, and fires only at the desktop viewport for the reason
described in Finding 1. Low effort to fix if desired (a one-line CSS override
for `.maplibregl-ctrl-attrib a`), but it is upstream-library-styled UI, not
this app's own component.

### 4. [Medium] `scrollable-region-focusable` (serious, axe rule) -- the Cases table's scroll container has no keyboard access

`CaseGrid.jsx`'s scrollable table wrapper (`.relative.overflow-auto.w-full`,
Radix `ScrollArea`'s viewport) can overflow (470 rows) but has no `tabindex`,
so a keyboard-only user cannot focus it to scroll with arrow keys -- they are
dependent on individual row/cell focus stops existing and being tabbable
through the full 470-row table, which is impractical. Fires on the Cases tab
at both viewports.

### 5. [Medium] `aria-hidden-focus` (serious, axe rule) -- Case Detail sheet

While the Case Detail sheet (Radix `Dialog`-based `Sheet`) is open, axe finds
a focusable element inside `#root` while `#root` (or an ancestor of the
flagged focusable element) carries `aria-hidden="true"` -- the standard
Radix "hide the background from the accessibility tree while a dialog is
open" mechanism, but landing on a node that is still reachable/focusable.
Fires at both viewports, immediately on opening the sheet (verified with
axe run *before* any of this script's own Tab-press/focus manipulation, to
rule out the check itself perturbing the result). Worth a focused look at
whether the Sheet's portal target and Radix's `aria-hidden` sibling-marking
are landing on the DOM as intended, since a background-content node remaining
both `aria-hidden` and focusable is exactly the combination that traps
screen-reader/keyboard users in a confusing state.

### 6. [Low] Touch targets under 44px -- tab triggers and the map zoom buttons

Consistent across every state/viewport: the three tab triggers ("Cases" /
"Statistics" / "Candidates", ~147x21px) and MapLibre's zoom +/- buttons
(~29x29px) are below the 44px touch-target guideline (WCAG 2.5.5 / Level
AAA, and the common mobile-platform minimum) -- height is the binding
constraint for all of them, width is already adequate. The Select filter
triggers (28px tall) and the sheet's Close button (33px tall) also fall
short. None of these are close to unusably small, but none meet the 44px
guideline either. Given Finding 1, the practical priority for mobile is
fixing the sidebar/map layout first -- these targets remain reachable today
regardless of viewport (the sidebar forces the whole page wider rather than
clipping its own contents off-screen), just at less-than-ideal size for
touch.

### 7. [Informational] `@pr-federation/react` v0.3.0 has a materially smaller export surface than the current federation convention, and no `test-harness.contract.json`

Confirmed by direct inspection of the resolved package
(`dashboard/node_modules/@pr-federation/react/src/index.jsx`): the pinned
`0.3.0` tarball exports exactly 10 symbols (`FederationThemeProvider`,
`useFederationTheme`, `FederationButton`, `FederationPanel`,
`FEDERATION_STATUS_ROLES`, `federationStatusRole`, `federationTone`,
`FederationStatusBadge`, `FederationEmptyState`, `FederationStatCard`). The
broader set referenced by the current federation convention
(`FederationIconButton`, `FederationSemanticBadge`,
`FederationEvidenceTierBadge`, `FederationConfidenceBadge`,
`FederationProvenanceBadge`, `FederationFreshnessBadge`,
`FederationSourceBadge`, loading/error/empty/offline/degraded/partial/
stale/async state components, and others) is not present at this pin and
cannot be imported without upgrading. A filesystem search of the resolved
package for `*contract*` also confirms `test-harness.contract.json` does not
ship in `0.3.0` -- that export path is only available from `v0.4.0-rc.1`
onward, so this repo cannot currently consume the shared contract-test
harness. This is real, structural version skew, not a usage bug in this
repo; recorded here as the audit's design-system-currency data point per
`docs/design-system-usage.json`.

## Scope limitations

- Two viewports (390x844, 1280x800) and one reachable theme (dark) only, per
  the task's fixed scope -- see Method above for why a distinct light theme
  does not exist to capture.
- Automated tooling only (axe-core 4.12.1 rule engine + this audit's three
  scripted checks); no manual screen-reader walkthrough.
- Four in-page states exercised (Cases tab, Case Detail sheet, Statistics
  tab, Candidates tab); CaseGrid's search/decade/tier filter *combinations*
  and the Select components' own open-dropdown state were not separately
  scanned.
- Map drag/scroll gestures were not exercised (consistent with
  `docs/GUI_AUDIT.md`, which notes the same tooling gap); this audit adds
  that OSM tile requests were also explicitly blocked at the network layer
  to keep `networkidle` navigation deterministic in this offline sandbox --
  this has no bearing on any of the findings above, all of which are about
  in-page app/library markup, not map tile rendering.
- This pass does not re-verify the Cases-tab map-rendering defect
  (`docs/GUI_AUDIT.md`'s "map renders as an invisible sliver" finding) at
  desktop width; it was out of scope for an a11y-focused pass and is already
  tracked there. Finding 1 above is a distinct, mobile-only defect (map
  width reaches 0px, not merely a sliver) confirmed independently in this
  session.
