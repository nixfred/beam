> Historical baseline report from Kimi3. Read the [review and final dispositions](../README.md) before acting on suggested fixes. These probes assert behavior of `99ee8b5`, including bugs.

# Beam independent audit: kimi3

Model: kimi-code-plan-global/k3 ("kimi3"). Baseline: commit 99ee8b5 (exported snapshot at
`<isolated baseline copy>`). All work and side effects stayed inside this copy and
system temp directories. No real Sunshine, hyprctl, systemctl, sudo, package manager, browser,
or LAN call was made; every OS interaction was faked or mocked.

## Commands run

- `python3 -m unittest discover -s tests -p 'test_*.py' -v` -> 70 tests, OK
- `node tests/service-state.test.js` -> 7 tests, OK
- `python3 -m unittest discover -s audit_tests -p 'test_*.py'` -> 39 tests, OK
- `node audit_tests/service-state-extra.test.js` -> 6 tests, OK

New adversarial files (all passing; bug-demonstrating tests assert the current defective
behavior with a `BUG:` comment so fixes can flip them):

- `audit_tests/audit_helpers.py` (shared Beam loader + FakeSystem)
- `audit_tests/test_pairing_adversarial.py`
- `audit_tests/test_qr_cache_poison.py`
- `audit_tests/test_firewall_parity.py`
- `audit_tests/test_virtual_edges.py`
- `audit_tests/test_display_edges.py`
- `audit_tests/test_action_flows.py`
- `audit_tests/service-state-extra.test.js`

## Confirmed findings (ranked)

### 1. Firewall saved-rules branch ignores tailscale rules (false "ports ready")
Severity: medium-low. `lib/beam.py:321-328` vs the active branch at `lib/beam.py:318-319`.
When `sudo -n ufw status` is not permitted, `firewall()` parses `/etc/ufw/user.rules` and
computes `firewallReady` from the 24 LAN rules only. The active-status branch additionally
requires one rule per port on `tailscale0` whenever that interface exists. A machine with
tailscale therefore reports `configured/ready` from saved rules but `incomplete` once ufw is
active and queryable, with the identical rule set. The saved branch also could not match
`in_tailscale0` tuple syntax even if the rules were present.
Trigger: tailscale host, sudo-n denied, complete v4 LAN rules in user.rules, no tailscale rules.
Impact: Beam claims streaming ports are ready while tailscale streaming would fail; state flips
across reboots/sudo availability.
Minimal fix: in the saved branch, parse `in_tailscale0` tuples and apply the same per-port
tailscale completeness check used in the active branch.
Test: `audit_tests/test_firewall_parity.py::test_saved_branch_ignores_tailscale_requirement`.

### 2. Corrupt cached QR file is served as success; UI retry loops forever
Severity: low-medium. `lib/beam.py:679`: cache hit is accepted when the file exists and is at
least 8 bytes, without checking the PNG magic that is verified right after generation at
`lib/beam.py:684`. `QrCode.qml` then fails to load the image, shows "Select to retry", and
every retry gets the same poisoned cache entry back with `ok: true`.
Trigger: a garbage file of 8+ bytes at `~/.cache/omarchy/beam/qr-<sha256>.png` (partial write,
disk corruption, another tool writing there).
Impact: QR permanently unavailable in the panel until the cache file is deleted by hand; the
UI gives no recovery that works.
Minimal fix: validate the 8-byte PNG signature on cache hits and regenerate on mismatch.
Test: `audit_tests/test_qr_cache_poison.py::test_corrupt_cached_file_is_reported_ready_without_validation`.

### 3. Valid-JSON but incomplete display session crashes with raw KeyError
Severity: low. `lib/beam_display.py:334` (`session["monitor"]` in `restore()`), reached from
`start()` at `lib/beam_display.py:353-354` and `stop()` at `lib/beam_display.py:389-390`.
`load()` only guarantees the file parses; a session dict missing `monitor` (truncated or
hand-edited `display-session.json`) raises KeyError, which is not a DisplayError, so the
stream-start prep-cmd and Restore display both die through `main()`'s generic handler with
"Beam could not finish this action." and no retry guidance. The same shape makes
`status()` degrade wholesale to `resolutionReady: False` (caught KeyError at
`lib/beam_display.py:261`), reporting "Use Repair to enable automatic iPad sizing" while the
app config is actually fine.
Trigger: `display-session.json` containing e.g. `{"token": "abc", "applied": {}, "requested": [1,2,3]}`.
Impact: confusing error, no recovery path offered; stream cannot start until the file is removed.
Minimal fix: validate required session keys in `load`/`restore` and raise DisplayError naming
the file and the Restore display action.
Tests: `audit_tests/test_display_edges.py::test_incomplete_session_json_crashes_with_key_error_not_display_error`
and `test_corrupt_session_file_degrades_status_without_hiding_readiness_cause`.

### 4. ValueError leaks from virtual restore when the source output is disabled mid-stream
Severity: low. `lib/beam_virtual.py:76`: `idle()` computes `max()` over non-virtual,
non-disabled monitors; on a single-monitor machine where the user disables the physical output
during a stream, the iterable is empty and `max()` raises ValueError. `restore()` at
`lib/beam_virtual.py:178` only catches DisplayError, so the session file is kept (good) but the
"Use Restore display." error annotation at `lib/beam_virtual.py:179-180` is skipped and the
user gets the generic failure message.
Trigger: disable the only physical monitor during a virtual-mode stream, then end the stream.
Impact: recovery state is retained, but the error is untyped and the guidance is lost.
Minimal fix: guard the empty sequence in `idle()` (or catch ValueError in `restore()`) and
raise DisplayError with the restore instruction.
Test: `audit_tests/test_virtual_edges.py::test_disabled_source_leaks_value_error_instead_of_display_error`.

### 5. `admin_port` and `config_values` disagree on duplicate `port` keys
Severity: low. `lib/beam_browser.py:23-25` returns on the first `port` line;
`lib/beam.py:253-260` keeps the last. With a duplicated `port` key in `sunshine.conf`
(possible after manual edits), Beam's admin/PIN URLs and its launcher port routing use the
first value while everything else that reads `config_values` uses the last.
Trigger: `sunshine.conf` with two `port = ...` lines.
Impact: Admin/PIN buttons open the wrong port; the pairing browser routing port can diverge
from the detected admin port.
Minimal fix: make `admin_port` iterate all lines and keep the last valid value, matching
`config_values`.
Test: `audit_tests/test_action_flows.py::AdminPortTests::test_duplicate_port_keys_first_wins_vs_config_values_last_wins`.

## Plausible risks (unconfirmed, need a real compositor/Sunshine/host)

- `DisplayFit.apply()` never passes `transform` on non-mirror `hl.monitor` calls
  (`lib/beam_display.py:301-304`). For a rotated physical monitor (transform 1/3), the apply
  and the restore paths both omit the transform; depending on whether Hyprland resets it, mode
  confirmation may fail (endless rollback) or rotation may be lost. The rotated test uses a
  fake compositor that ignores transform.
- `VirtualDisplay.restore()` focuses the workspace that was active on the virtual output
  (`lib/beam_virtual.py:177`). If that is the `beam-idle` workspace itself (user focused it
  mid-stream), Hyprland may pull it onto the physical monitor. Behavior is compositor-defined.
- `System.admin()` infers "login created" from a `/welcome` redirect to exactly `/`
  (`lib/beam.py:118`). Other Sunshine versions may answer differently; offline this cannot be
  verified.
- `qr()` cache pruning stats files between `glob` and `stat` (`lib/beam.py:691`); a concurrent
  prune by a second Beam process would raise OSError and report "The QR code could not be
  saved." despite a valid QR. Very low probability.
- Guided step 2 "Continue" (`BeamPanel.qml:103`) requires `hostReady` but not `qrAvailable`;
  a missing qrencode is only surfaced on step 3 by the QR error box. Truthful, but later than
  the "fail fast" spirit of the install checks.
- Audio streaming is only implicitly preserved (Beam never disables Sunshine audio); no client
  was available to verify.
- Law 17 (nothing scrolls, 1024x768 logical): the panel ships a `geometry()` IPC audit and the
  layout avoids clipping by construction, but actual rendering needs a live Omarchy shell, so
  no-scroll conformance is unverified here.

## What was verified clean (no defect found)

- `pairing_root()` streaming parser: credential-shaped decoys, nested `root` keys inside
  skipped values, escaped quotes, primitives, arrays, truncation, BOM, 4 MB cap. Never
  collects credential values and never raises (audit_tests/test_pairing_adversarial.py).
- `log_facts()`: encoder regex variants (`H.264`/`H264`, spacing, case), stale timestamps
  before process start ignored, half-written lines not consumed, log rotation/truncation
  handling, per-process identity binding (probe plus tests/test_backend.py).
- Action queue/state machine: pending/opening lifecycle, 20 s stale conversion with preserved
  id and truthful "closed before finishing" error, terminal reopen after staleness with a new
  id, spawn failure written as an error result, tty and root refusal
  (audit_tests/test_action_flows.py).
- Install: QR-first ordering, cancellation stops before any Sunshine change, no broken stock
  service-enable path, second install does not reinstall sunshine; idempotent repair migration
  to the browser-owned launcher (probe plus tests/test_backend.py).
- Undo: symlinked config refused and preserved, leftover package/rules reported truthfully,
  clean undo removes config and browser marker (audit_tests/test_action_flows.py).
- Display: all 17 profiles/10 sizes/45 models produce compositor-clean scales via
  `readable_scale` + `validate_scale`; 2732x2048 at 4/3 gives the exact 2049x1536 workspace;
  reselecting the same size preserves custom scale; profile changes only affect the next
  stream; 5120x1440@1 restore; manual changes preserved; token mismatch cannot restore a
  superseded session; two-process refusal happens before any mode change
  (audit_tests/test_virtual_edges.py, test_display_edges.py, plus existing suite).
- Browser routing: only exact `https://localhost|127.0.0.1|[::1]:<port>` single URLs are
  rerouted to the private browser; userinfo, trailing-dot hosts, wrong ports, non-https and
  multi-arg invocations fall back to the real xdg-open (probe plus tests/test_browser.py).
- `stock_function()`: missing marker and missing function both fail truthfully; env injection
  for the admin web app uses an argv array, interactive, no password handling (probe).
- `processes()`: zombie exclusion, WAYLAND_DISPLAY filtering, starttime identity, browser
  ownership record (probe plus tests/test_backend.py).
- `status()` output conforms to `ServiceState.decodeStatus` requirements in both normal and
  fallback shapes; JSON-serializable (probe).
- `ServiceState.js`: type confusion, stale streaming clamp, nextStep bounds, report state
  mapping, timestamp normalization including numeric-string rejection, queue dedupe/overflow,
  freshness window bounds (audit_tests/service-state-extra.test.js).
- Machine-agnosticism: no VM/laptop/GPU-specific code paths found; encoder truthfully comes
  only from Sunshine's log line.
- No password handling anywhere: sudo steps run interactively in the visible terminal; the
  Sunshine admin password is never read (pairing parser skips credential fields structurally).

## Coverage limitations

- Real Hyprland/Sunshine behavior (mode application with transforms, mirror semantics,
  workspace focus rules, headless output lifecycle) is mocked; findings in that layer are
  listed as unconfirmed risks.
- QML rendering was not executed (no shell available); only the pure JS state rules were run.
- `prototype/` was treated as reference per CLAUDE.md and not audited.
- The live-host style references in `docs/` and the normative PRD sections that require
  hardware (actual iPad pairing, audio, Moonlight Custom negotiation) are out of scope for an
  offline sandbox.
