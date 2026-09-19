# Beam verification

This is development evidence, not a claim of complete physical iPad acceptance.
Raw VM captures and diagnostic JSON remain local. The public screenshots use a
documentation address, supplied to the UI before native capture.

## Automated checks

- Ten backend regressions cover firewall readiness, log freshness, notification
  routing, exited-child handling during removal, and shared private-browser Admin/PIN
  launches with fallback and error reporting, plus running-process migration and
  refusal to restart an active stream.
- Nine browser regressions cover local-origin matching, unrelated-link fallback,
  custom ports, idempotent startup migration, backup preservation, removal, duplicate
  startup repair, PID reuse rejection, and a real child-process notification route that restores the
  browser's original command search path. The native launcher test also checks that
  display preparation precedes capture and failure prevents a wrong-display launch.
- Twenty-nine display regressions cover native and fallback mode selection, a
  5120x1440 starting desktop, client dimension validation, preservation of
  Sunshine apps, mode rollback, multi-monitor selection, disconnect/crash
  recovery, rotated outputs, preservation of manual display changes, migration of
  the unmodified Desktop tile, preservation of customized/ambiguous desktop apps,
  fixed-mode persistence, a 720p client mismatch, scale restoration, returning to
  automatic sizing, and refusal to replace an unavailable fixed mode with a smaller one.
  Client mismatch evidence survives disconnect, clears after a matching request,
  stores only validated dimensions, and tolerates absent or malformed diagnostics.
- Fourteen additional native-display regressions cover iPad pixel dimensions and readable
  scaling, exact sizing independent of EDID, durable rollback, failed recovery,
  manual changes, unplugged source recovery, newly opened workspaces, multiple
  source selection, disabled laptop panels, fixed native sizes, missing capture outputs, and a 1920x1440 custom workspace
  staying at 100% scale while auto mode retains its native scaling policy.
  Explicit 4/3 scaling at 2732x2048 gives 2049x1536 logical pixels, survives
  restoration, tolerates compositor float precision, and rejects invalid
  scales without overwriting the saved preference.
- Seven service-state tests cover stale/malformed status, action queues,
  terminal progress, error recovery, and idle-inhibitor eligibility.
- The Omarchy manifest validator and whitespace checks pass.

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
node tests/service-state.test.js
omarchy-plugin-validate .
git diff --check
```

## Live checks

The user confirmed physical iPad pairing, desktop video and audio. Sunshine's log
showed `Executing [Desktop]`, with no Beam sizing session, explaining why that first
stream retained the 5120x1440 desktop. Setup now equips the unmodified Desktop tile
with the same preparation, foreground supervisor and undo hooks as Beam Desktop.
Both paths still require a fresh launch after choosing the Moonlight resolution.

A subsequent physical iPad launch of Beam Desktop sent **1280x720 at 60 FPS**.
The preparation hook ran, saved the original 5120x1440 layout, and Hyprland and
Sunshine both confirmed a 1280x720 desktop at scale 1 while streaming. This
confirms real client-size negotiation and resizing. The user reported the UI
looked oversized at 720p. A later 2560x1440 physical-mode pin made text too
small and retained borders, while Moonlight still requested 1280x720. The native
virtual-display implementation supersedes that workaround; Full quality remains
to be checked on the physical iPad.

The host's Sunshine startup was migrated to the notification-browser helper with
a backup. One running process, matching PID/start-time ownership, configured login,
automatic sizing and setup readiness were verified afterward. Hyprland reload and
configuration validation passed. The login and pairing panels fit the 5120x1440
host. Clicking a new physical-device pairing notification still needs user
confirmation; neither a web PIN acknowledgement nor these checks prove pairing.

An isolated Omarchy 4.0.2 / Hyprland 0.56.2 VM was used for clean Sunshine
installation and removal. Installation recovered from the packaged service-name
mismatch and ended with one Sunshine process and complete streaming firewall
rules. Removal left no Sunshine processes, startup entry, or streaming rules.
The install terminal remained open during removal to verify child reaping.

The original guided and expert layouts, long action errors, and removal
confirmation fit at 1280x800 in dark and light themes. Both QR codes decoded
from screenshots with software. Normal views also fit on a 5120x1440 host.
A real Wayland idle observer responded to synthetic Sunshine connect/disconnect
events and confirmed that the hold released afterward.

The original physical-mode sizing implementation received the actual Moonlight request through
Sunshine's preparation environment. A foreground Beam Desktop app observes the
current Sunshine process and stream log, ends after the last client disconnects,
and restores the saved mode. Sunshine's undo hook also restores it on quit.
No physical monitor modeline is invented: only advertised modes are selected.

Live sizing was exercised with the VM desktop set to 5120x1440. A synthetic
2048x1536 Moonlight request selected its supported 1920x1440 mode. Synthetic
connect/disconnect events restored 5120x1440. An exact 1920x1080 request also
worked; killing the VM's Sunshine process restored 5120x1440. The VM was then
returned to its original 1280x800 layout. These were real compositor mode changes
and production helper processes, with simulated client requests and log events.

All six guided steps, active sizing in Expert, and a combined action error and
Remove confirmation fit at 1024x768. Current public captures also fit at
1280x800 in dark and light themes. Changing a theme may reload the user's normal
monitor configuration; the session supervisor ends the resized session instead
of continuing to capture an unintended size, preserving that newer layout.

## Native virtual-display verification

The dedicated VM created a normally initialized headless output and Sunshine
2026.516 captured it with its software H.264 encoder. Initializing the output
as a mirror caused capture discovery to fail, so Beam keeps a normal named
headless output and mirrors only the physical screen during a stream.

Production Beam code exercised exact 2752x2064, 2360x1640 and 2048x1536 modes at
200% scale, verified the physical display's mirror target, and restored its
original mode, position and scale after every session. Physical workspaces
returned and only the empty named workspace remained on the capture output.
A fresh startup preserved the physical layout. The real supervisor restored
after simulated disconnect log events and after stopping the actual VM Sunshine
process. Expert, Connect and Watch fit at 1024x768 logical resolution after
hotplug settled. A screenshot exposed a temporary overlap warning; staging the
resize off-screen before mirroring, and parking it before restoration, removed
that warning in the final native capture.

The live host now runs one Sunshine with hardware `h264_vaapi`, its original
login and one paired iPad, and the native capture output. An idle-host synthetic
2360x1640 request applied at scale 2 and restored the original 5120x1440 physical
layout. The earlier 2560x1440 pin was removed. These compositor tests do not
substitute for a new physical iPad connection using Full.

## Custom middle-ground follow-up

The user identified the iPad size as 2732x2048. Live compositor verification on
the host applied that exact pixel size at 1.3333334 reported scale, producing a
2049x1536 logical workspace. The original physical mode and layout restored,
and the 2732x2048, 60 FPS, 4/3-scale preference is saved for subsequent streams.
A 1920x1440 custom-size check also confirmed a full 1920x1440 workspace at scale
1. These checks used synthetic client dimensions; the next physical connection
must request 2732x2048 to verify final appearance. The last observed physical
client had still requested 1280x720.

## Borders on all four sides

A physical iPad screenshot showed a 4:3 desktop inset on all four sides.
The next live session and a user-requested webcam inspection confirmed the
inset picture and a **1280x720 client request** against a
**2732x2048 capture at 4/3 scale**. The compositor capture itself filled its
frame. This is consistent with a 4:3 picture pillarboxed inside 16:9 video,
which is then letterboxed onto the iPad. The matching Moonlight custom setting
is still required; host dimensions alone do not establish video dimensions.

Beam now retains the last validated client dimensions separately from recovery
state, so the mismatch remains visible after the stream closes. The diagnostic
contains no client identity, credentials, or other environment variables.
62 Python tests, 7 JavaScript tests, manifest validation and whitespace checks pass.

## Remaining acceptance

Physical iPad pairing, video, audio and a requested 720p resize are confirmed.
Still needed: camera scanning, Full/Safe Area requests, image quality, input,
and restoration after a real resized stream disconnects.
Native sizing now removes the physical panel mode limit. Full still must be
selected in Moonlight; a 720p or fixed 16:9 request can leave borders.

After changing Moonlight's resolution, quit the existing session and launch
Beam Desktop again. Sunshine does not rerun preparation hooks for a resume.

## Protocol references

- [Sunshine application preparation commands](https://docs.lizardbyte.dev/projects/sunshine/latest/md_docs_2app__examples.html)
- [Sunshine app lifecycle and client dimension environment](https://github.com/LizardByte/Sunshine/blob/master/src/process.cpp)
- [Moonlight iOS Full and Safe Area sizing](https://github.com/moonlight-stream/moonlight-ios/blob/master/Limelight/ViewControllers/SettingsViewController.m)

These references informed the implementation; the tests and local VM checks
establish what has actually been exercised here.

## Model picker and installer follow-up (2026-09-19)

- Fresh setup now installs the Sunshine package directly and reuses only the
  stock firewall/admin-web-app functions, avoiding the missing `sunshine.service`
  enable step. In the isolated acceptance VM, removal completed, the package was
  absent, and the production installer then completed through a terminal PTY.
  Its transcript contains no missing-unit error or mismatch-recovery message.
  Readback: one Sunshine process, packaged unit disabled, managed startup and
  browser routing ready, firewall ready, native display ready, `setupReady: true`,
  and `adminConfigured: false` awaiting the human's new login.
- **77 checks pass:** 70 Python tests and seven service-state tests. New coverage
  checks failed package transactions, a missing package after an apparent success,
  all 17 iPad presets, exact native capture and ultrawide restoration, persistence,
  preserving same-size custom scaling, invalid model IDs, pre-install rejection,
  and switching back to Full. These display tests use synthetic client requests.
- The offline catalog covers all 45 models in Apple's identification list as
  checked on 19 September 2026. Every model has its own technical-specification
  source in [the resolution guide](../ipad-resolutions.md) and `lib/ipads.json`.
  Ten resolutions are grouped into 17 family/model choices. Native pixel counts
  are verified specifications, not a claim that every legacy iPad runs Moonlight.
- All four family views fit at **1024x768 logical pixels**, including the six-row
  Pro list. Native capture used **2048x1536 at scale 2**. Geometry reported zero
  clipped text. Saved-size and error reports were injected as VM presentation
  fixtures and also fit; both were visually inspected. The native light-theme
  [picker capture](../assets/ipad-picker.png) is public and contains no private
  account or network data. A dormant second display can produce a stale capture;
  final visual verification used the actual active iPad output.
- The host's dark-theme picker and guided steps 3, 5 and 6 fit with its enlarged
  fonts at **2049x1536 logical pixels**. The shell's component cache required one
  shell refresh to load the new UI. Sunshine was not restarted. Afterward, the
  live host still reported one process and **2732x2048, Moonlight matches**, at
  the user's existing **4/3 scale**.
- Local wallpaper playback was disabled separately at the user's request. The
  installer does not globally change another user's wallpaper preference.
