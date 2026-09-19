# Beam follow-up verification, 2026-09-19

Continued from Kimi3's `de9ad8e` and `0bfe179` implementation. This is local
development evidence, not a declaration that all Beam 1.0 acceptance is complete.
These checks preceded the initial public snapshot of
[`nixfred/beam`](https://github.com/nixfred/beam). The referenced Kimi3 commits
remain in local development history; the public repository starts with the
reviewed implementation, documentation, and graphics together.

## Fixed

- The welcome notification called a nonexistent `plugins openPanel` IPC target.
  It now calls Beam's actual `nixfred.beam open` target.
- The panel treated any firewall rule as success and computed a weaker readiness
  result than the backend. Both views now use `firewallReady` and `setupReady`.
- Reopening the wizard retained its old page. Each opening now selects the
  backend's current unfinished step. Completed steps also show their checkmarks.
- Install was disabled if Sunshine existed but the QR helper was missing. That
  recovery action remains available, with a matching QR error instruction.
- The App Store action now uses the service/helper action path. Certificate
  guidance shows the actual detected local admin URL.
- Removal failed if Sunshine had exited while its original installation terminal
  remained open. Background children are now reaped while that terminal waits,
  and zombie processes cannot block the stop check. Stop errors during removal
  also retain the correct removal retry action.
- The layout audit now checks horizontal text overflow as well as vertical bounds.

## Executed checks

`omarchy-plugin-validate .`, six Python backend tests, seven JavaScript service
tests, and `git diff --check` pass. Reproduce the tests with:

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
node tests/service-state.test.js
omarchy-plugin-validate .
```

An independent `test-drive-beam-acceptance-20260919` VM was created from the
`plugin` checkpoint. It began with no Sunshine, at 1280x800 logical resolution.
The address visible in the VM captures and JSON is its disposable libvirt NAT
test address, not a physical host, home-network, or tailnet address. This was
confirmed against the VM's interface and DHCP lease before publication.
Its packaged installer hit the service-name mismatch; Beam repaired it. All five
checks became true: one process, 27 LAN firewall rules, one startup path, detected
display, and installed Sunshine. Its own log reported `libx264`; Beam recommended
1920x1080 at 60fps and 20 Mbps. See [installed facts](vm-installed.json).

Opening the panel after installation selected step 4. All six guided pages and
the expert view fit. Synthetic long action errors and the Remove confirmation
fit together in dark and light themes. Each captured layout has a matching JSON
file containing visible text bounds, content dimensions, and `fits: true`.
Screenshots were visually inspected, including edges and footer controls.

Representative captures:

- [Guided installation result](vm-guided-2.png)
- [Expert error plus Remove confirmation](vm-expert-error-confirm.png)
- [Guided long error](vm-guided-error.png)
- [Light theme expert view](vm-expert-light.png)
- [Light theme App Store QR](vm-guided-light-qr.png)

`zbarimg --quiet --nodbus` decoded both the App Store URL and the VM address from
the dark and light expert screenshots. This is software decoding, not an iPad
camera test.

The awake hold was checked with a separate real Wayland `IdleMonitor` configured
to respect inhibitors. Synthetic current-process CONNECTED/DISCONNECTED log
events produced idle=true before, idle=false during streaming, and idle=true
after disconnect. The plugin's real service and bar inhibitor were used; no host
idle setting changed. See [idle observation](vm-idle-inhibitor.json). This does
not substitute for a real Moonlight streaming session.

Removal was repeated after reinstalling with the child-reaping fix, leaving the
installation terminal open to reproduce the original failure. Sunshine was
removed, `pgrep -x sunshine` was empty, autostart was absent, and there were zero
Sunshine firewall rules. See [removal facts](vm-removed.json).

Only the isolated VM had a temporary IPC hook to display the confirmation state.
It was overwritten with the final uninstrumented source before the final install
and removal cycle. Synthetic errors used the existing action-result file, not a
production test mode. The task VM was stopped after checking its desktop health;
the standby and templates were preserved.

Both normal panel modes were also rendered and measured on the 5120x1440 host.
See `host-*-bounds.json`. Host screenshots contain private desktop data and are
kept outside this public repository. Beam is linked to this source; the host
shell was restarted to load QML changes after a rescan retained cached code.
Sunshine was installed and removed only in the test VM.

## Remaining acceptance

- Real iPad camera scanning, login creation, pairing and automatic advancement,
  picture/input quality, and real stream transitions still need an iPad.
- The host's normal guided/expert views were checked; long-error and confirmation
  screenshots were captured in the smaller VM, not on the host.
- The missing-QR recovery branch was reviewed and validated, but its complete
  package-recovery interaction was not separately exercised.
- The initial welcome's once-only behavior has a backend regression test. A real
  notification click was not driven; its corrected IPC command was run directly.

OMW-PLUGIN-NO-SCROLL: all captured views fit with readable theme-derived text,
without scrolling, clipping, or elision. The evidence does not claim arbitrary
font-scale or screen-size coverage. `source-hashes.json` identifies the final
runtime sources; the last QR recovery wording change does not appear in the
earlier screenshots because their QR helpers were installed.
