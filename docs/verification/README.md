# Beam verification

This is development evidence, not a claim of complete physical iPad acceptance.
Raw VM captures and diagnostic JSON remain local. The public screenshots use a
documentation address, supplied to the UI before native capture.

## Automated checks

- Ten backend regressions cover firewall readiness, log freshness, notification
  routing, exited-child handling during removal, and shared private-browser Admin/PIN
  launches with fallback and error reporting, plus running-process migration and
  refusal to restart an active stream.
- Eight browser regressions cover local-origin matching, unrelated-link fallback,
  custom ports, idempotent startup migration, backup preservation, removal, duplicate
  startup repair, PID reuse rejection, and a real child-process notification route that restores the
  browser's original command search path.
- Eighteen display regressions cover native and fallback mode selection, a
  5120x1440 starting desktop, client dimension validation, preservation of
  Sunshine apps, mode rollback, multi-monitor selection, disconnect/crash
  recovery, rotated outputs, and preservation of manual display changes.
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

The current sizing implementation receives the actual Moonlight request through
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

## Remaining acceptance

A physical iPad is still needed to check camera scanning, Sunshine login,
pairing, Full/Safe Area requests, image quality, input, and a real streamed
disconnect. The chosen fallback may have less detail or small borders when
the physical monitor cannot display the requested native size.

After changing Moonlight's resolution, quit the existing session and launch
Beam Desktop again. Sunshine does not rerun preparation hooks for a resume.

## Protocol references

- [Sunshine application preparation commands](https://docs.lizardbyte.dev/projects/sunshine/latest/md_docs_2app__examples.html)
- [Sunshine app lifecycle and client dimension environment](https://github.com/LizardByte/Sunshine/blob/master/src/process.cpp)
- [Moonlight iOS Full and Safe Area sizing](https://github.com/moonlight-stream/moonlight-ios/blob/master/Limelight/ViewControllers/SettingsViewController.m)

These references informed the implementation; the tests and local VM checks
establish what has actually been exercised here.
