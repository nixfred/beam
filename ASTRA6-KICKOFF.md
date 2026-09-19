# Astra6: build Beam

You are building **an Omarchy Quickshell plugin**. Not a script, not a CLI tool, not a
service. A plugin that a stranger installs from the Omarchy plugin catalogue, after which a
dot appears in their bar, and clicking that dot walks them from knowing nothing to watching
this desktop on an iPad.

Read `PRD.md` in full before writing anything. It is normative. This note only tells you how
to approach it and what will get the work rejected.

## The deliverable

Six files in the repo root, laid out exactly as PRD section 5 specifies:

```
manifest.json      kinds: service, bar-widget, panel
BarWidget.qml      one dot in the bar, always visible
BeamPanel.qml      the guided wizard and the expert screen
Service.qml        state, polling, action queue
QrCode.qml         QR rendering
bin/omarchy-beam   internal helper, shipped inside the plugin
```

**The product is the QML.** The bar dot and the panel are the entire thing a user ever
touches. Most of your effort belongs there.

**The bash helper is an internal implementation detail.** It exists so the QML has one honest
source of facts instead of shelling out from six places. A user never runs it, never sees its
name, and it is never installed to `PATH`. Do not add user-facing commands to it. Do not let
it grow into the product. If someone could look at what you built and reasonably call it "a
shell script with a GUI bolted on", start again.

## How to work

- **Verify by executing, never by reading.** Every factual claim in PRD section 4 was
  established by running something, and one real bug (`pgrep -c` printing `0` and exiting
  non-zero) was found that way after the code looked correct. Assume the same is true of
  whatever you write.
- **`prototype/` is reference, not gospel.** It holds an earlier cut. The helper in it has
  been run and its JSON validates; the QML in it has never been loaded into a shell and is
  unverified line for line. Read it to see how something was done. Do not copy it wholesale,
  and where it disagrees with the PRD, the PRD wins.
- **PRD section 9 is not advice.** Every gotcha in it has already cost this codebase or a
  sibling plugin real time. `WidgetButton` has no `contentItem`. Pointer handlers do not fire
  in these panels, use `MouseArea`. `Rectangle.border.width` defaults to 1. Never mutate a
  QML `var` array in place. Never name a panel file `Panel.qml`.
- **`omarchy-plugin-validate` is the first gate,** not the last check.

## What will get it rejected

1. **Any host-specific code path.** No branch on laptop versus desktop versus VM, no GPU
   detection, no assumptions about Proxmox. If there is an Omarchy session with a display and
   an address, Beam works. This project began as a VM-specific runbook and was deliberately
   widened; do not let that creep back.
2. **Inferring the encoder from a DRM device.** virtio-gpu exposes `/dev/dri/renderD128` and
   cannot encode a single frame. The only permitted source is Sunshine's own
   `Found H.264 encoder:` log line. This is a correctness rule, not a style preference.
3. **Information that requires scrolling.** No scroller in either panel mode or any
   subsection, including action results. Show a complete, concise action report instead of
   a scrolling log. Use width and grouped columns; do not clip, hide overflow behind tabs,
   or make text unreadable. Screenshot both modes on the host and at 1280x800 logical
   resolution, including errors and confirmations. Inspect every edge. Follow the live
   plugin references in `docs/style-reference.md`.
4. **Touching a password.** Never handle a sudo password: the one root step opens a terminal
   the human types into. Never create, store or read the Sunshine admin password: detect only
   that a `username` line exists in `sunshine.conf`.
5. **Any absolute user path.** No `/home/pi`, no `/home/<anyone>`. The helper's path resolves
   relative to the QML file. This plugin is for strangers.
6. **Claiming something works that you did not run.** Say what you verified, how, and what you
   could not. An honest "I could not test the pairing step without an iPad" is worth more than
   a green checkmark that means nothing.

## Definition of done

PRD section 10, all sixteen criteria, on a machine where Sunshine was never installed. The
ones people skip: `processes` is exactly 1 after install, not 0 and not 2; both QR codes are
readable by a phone camera **in a dark theme and a light theme**; the awake-hold fires on the
transition into streaming and releases on the transition out; and the wizard opens on the
first unfinished step rather than always at step 1.

## Report back

What you built, what you ran to prove each part, what failed and how you fixed it, and an
explicit list of anything you could not verify and why. Findings and claims will be checked by
execution before they are trusted, so flag your own uncertainty rather than letting it be
discovered.
