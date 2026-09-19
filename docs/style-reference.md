# Beam host style references

Inspected on 2026-09-19 through the running Omarchy shell's plugin registry, live panels,
local screenshots and installed QML. The active display was 5120x1440 at scale 1. These
observations establish a visual direction, not proof that every existing plugin fits every
screen. Screenshots remain outside the repository because they contain private host data.

## User requirement

Plugins must never require scrolling to see their information. All information and controls
for the displayed plugin view must fit at readable sizes. No internal-scroller exception,
clipped bottom rows, hidden overflow tabs or required text reduced to ellipses. Beam retains
the deliberate guided setup steps from the PRD; each step must fit completely. Its expert
view shows all operational information together.

## Panels inspected live

| Reference | Observed treatment | Apply to Beam |
| --- | --- | --- |
| Lamplight, `nixfred.lamplight`, 1.0.0 | Wide, shallow panel; live header; nine mode cards in three columns; full-width brightness and palette rows | Group related controls in visible rows; use horizontal space; put live status in the header |
| Burn Bar, `nixfred.burnbar`, 1.20.0 | Dense dashboard; prominent totals; colored metric cards; side-by-side charts, limits and local-compute readings; compact footer | Give current stream state a clear hierarchy and keep technical facts aligned and simultaneously visible |
| Tesla, `jankeesvw.tesla`, 1.5.0 | Four columns containing a visual summary, controls and compact labeled data sections; complete panel visible on this display | Arrange status, actions and connection details across columns; keep every operational field visible |
| Detailed Weather, `io.github.calebhat.weather`, 1.3.2 | Large current reading; horizontal forecast rows; compact two-column metric cards | Lead with the answer, then organize supporting details into clear groups |
| Chronos, `nixfred.chronos`, 1.0.0 | Day ring and month heading; compact calendar; progress rail and moon detail; restrained accent | Use a simple status motif and meaningful motion without consuming the space needed for information |

Weather's current live panel was a compact forecast grid. Its source also contains orbital
effects; do not claim those were active from this inspection. Lamplight's source comments
mention four columns, but the live layout and actual grid use three. Prefer observed behavior
over stale comments.

## Shared visual direction

- Use the active shell theme's background, foreground, accent and font. The dark palette
  observed here is a reference, not a set of colors to hardcode. QR codes keep their white
  backing and quiet zone in every theme.
- Use thin outlines, modest corner radii, low-opacity selected fills and restrained dividers.
- Keep headings and labels compact. Align numbers, units and status values; use monospace
  for addresses and technical readouts. Reserve large type for the main state or next action.
- Put related facts in visible sections and columns, with actions near the state they affect.
- Animate state changes and useful live indicators. Existing QML provides references for
  reveals, count transitions and pulses; gate ongoing effects on visibility and relevance.
- Keep the plugin visibly part of the bar and shell, with consistent anchoring and Escape
  dismissal. Keep controls and the bottom edge visible, including during errors.

## Beam layout direction

Keep a compact header with the Beam dot, current state and Guided/Expert switch. Guided mode
has its step rail, a stable stage and visible navigation. Expert mode groups all status,
connection details, actions and the complete current action report across the available
width. Do not copy the prototype's scrolling log box.

Test both modes with realistic long values, missing dependencies, action errors and the
Remove confirmation. Verify on the real host and at 1280x800 logical resolution before
claiming the no-scroll requirement is met. The existing prototype has not been changed or
visually verified by this style study.
