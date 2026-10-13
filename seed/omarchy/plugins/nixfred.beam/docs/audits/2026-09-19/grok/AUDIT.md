> Historical baseline report from Grok 4.6. Findings are not all accepted as written. Read the [review and final dispositions](../README.md) before acting on this report. These probes assert behavior of `99ee8b5`, including bugs.

# Beam grok audit

Model: Grok 4.6 (xAI), independent grok audit of an isolated Beam copy. Baseline named by the user: commit 99ee8b5. This tree is not a git checkout (`git rev-parse` failed), so that hash was not re-verified here. Production files were not edited. No live Sunshine, hyprctl, systemctl, sudo, test-drive, package manager, GUI, LAN, or secret files were used.

## Commands and results

```
python -m unittest discover -s tests -p 'test_*.py' -v
```
70 tests, OK, 0.545s.

```
node tests/service-state.test.js
```
7 tests, pass.

```
python -m unittest discover -s audit_tests -p 'test_*.py' -v
```
28 tests, OK, 2.051s. Repro file: `audit_tests/test_audit_adversarial.py`.

```
node audit_tests/service-state-audit.test.js
```
5 tests, pass. Repro file: `audit_tests/service-state-audit.test.js`.

Existing tests do not cover the confirmed defects below. Passing the baseline suite is not sufficient.

## Confirmed findings (ranked)

### 1. High: restoring a virtual session after BEAM-IPAD disappears leaves the physical display mirrored and deletes recovery

- File:line: `lib/beam_virtual.py:159-183`
- Trigger: Start a native session, then lose the headless output (failed `hyprctl output remove`, compositor drop, or Repair racing a stream). Call `stream-stop` / `restore-display` / `supervise` finally.
- Impact: `mirrored` is computed only as `virtual and source.mirrorOf == virtual.id`. If `OUTPUT` is missing, unmirror is skipped, workspaces may still move, then `display-session.json` is unlinked and the call returns success. The physical screen stays mirrored to a dead id. Restore display then reports no active resize.
- Minimal fix: If `source.mirrorOf` is not `none`, unmirror using `session["sourceOriginal"]` even when `OUTPUT` is gone. Unlink recovery only after that apply confirms. If unmirror cannot run, keep state and raise.
- Test: `audit_tests/test_audit_adversarial.py::AuditVirtual.test_missing_virtual_output_clears_recovery_while_leaving_mirror`

### 2. High: stream flag is a counter, so an extra CLIENT CONNECTED plus one DISCONNECTED stays live

- File:line: `lib/beam.py:397-401` (cache persist at 402). Supervisor uses this at `lib/beam_display.py:429-433`.
- Trigger: Sunshine log for the current process contains two `CLIENT CONNECTED` lines and one `CLIENT DISCONNECTED` (duplicate connect, reconnect, or a second client). PRD 6.4 says streaming is the last matching CONNECTED/DISCONNECTED line.
- Impact: `streamCount` remains 1, `streaming` stays true, the bar/idle inhibitor stay live, and `supervise` keeps refreshing `last_live` so it will not time out after disconnect. The ultrawide layout is not restored until Sunshine exits or the monitor no longer matches.
- Minimal fix: Track the last matching connect/disconnect line (and/or clamp to 0 on disconnect for this product's single client). Treat incomplete cached `facts` as empty. Catch `KeyError` and `AttributeError` in `log_facts`.
- Test: `audit_tests/test_audit_adversarial.py::AuditBackend.test_duplicate_connected_then_disconnect_stays_streaming`

### 3. High: non-object action.json / log.json crash status into the probe fallback

- File:line: `lib/beam.py:49-53` (`read_json` returns any JSON value), `407-409` (`action_state` calls `.get`), `354-357` and `404-405` (`log_facts` calls `.get` and does not catch `AttributeError`/`KeyError`).
- Trigger: `action.json` is `[]`, `null`, `true`, `1`, or `"busy"`; or `log.json` is `null`; or cached `facts` omit `streamCount` while a CONNECTED line arrives; or `updatedAt` is a non-number while `phase` is `opening`.
- Impact: `status()` raises. `main` substitutes `fallback_status()`, so the panel shows "Beam could not check this computer", drops the iPad catalog, and clears live checks. A half-written or type-confused cache file is enough. Incomplete `facts` also raises `KeyError` on every later poll because the offset is not advanced.
- Minimal fix: If `read_json` does not return a `dict`, use `{}`. In `action_state`, coerce `updatedAt` with a numeric check. In `log_facts`, require `facts` to be a dict with `streamCount`, and catch `AttributeError`/`KeyError`.
- Tests: `test_action_json_array_crashes_status_into_generic_failure`, `test_action_json_null_and_non_object_are_not_normalized`, `test_opening_action_with_non_numeric_timestamp_crashes_status`, `test_log_json_non_object_is_not_caught_by_log_facts`, `test_incomplete_cached_facts_raise_keyerror_on_connect_line`

### 4. Medium: Repair that rewrites display-virtual.json wipes the saved iPad size and 4/3 scale

- File:line: `lib/beam_virtual.py:109-120`
- Trigger: `display-virtual.json` `entry` changes (plugin path move, copy, or any Repair where the stored launcher path is not exactly `self.beam.entry`). User already saved 2732x2048 at scale 4/3 (Air 13 / Pro 12.9).
- Impact: `install()` always `unlink`s `display-preferences.json` when the virtual record is not byte-for-byte `expected`. The next stream uses automatic scale 2 instead of the saved 4/3 middle ground. Same-size reselect would have preserved that scale; Repair does not.
- Minimal fix: Update `entry`/`output` in place. Only clear display preferences when migrating a known old 16:9 pin, not on launcher-path refresh.
- Test: `audit_tests/test_audit_adversarial.py::AuditVirtual.test_plugin_path_change_wipes_saved_ipad_and_custom_scale`

### 5. Medium: virtual remove ignores hyprctl failure, then Repair cannot recreate the capture output

- File:line: `lib/beam_virtual.py:185-190`
- Trigger: `hyprctl output remove BEAM-IPAD` returns non-zero (the isolated DisplaySystem stub does this). `remove()` still unlinks `display-virtual.json`.
- Impact: Headless output remains. Next `virtual.install()` sees no prefs plus an existing `BEAM-IPAD` and raises "Another display already uses Beam's capture name." Undo/Repair cannot finish native sizing without a manual output rename.
- Minimal fix: Treat non-`ok` remove as failure and keep preferences. Retry remove before considering the name free.
- Test: `audit_tests/test_audit_adversarial.py::AuditVirtual.test_remove_unlinks_prefs_after_failed_output_delete`

### 6. Medium: virtual remove no-ops when preferences are already gone, leaking BEAM-IPAD

- File:line: `lib/beam_virtual.py:185-186` (`if self.enabled()`)
- Trigger: `display-virtual.json` missing or falsy while the headless output still exists (partial undo, failed remove, manual file delete).
- Impact: `undo` and `remove()` leave the capture output. Same reinstall deadlock as finding 5.
- Minimal fix: If `OUTPUT` is present, remove it regardless of the prefs file, then unlink prefs.
- Test: `audit_tests/test_audit_adversarial.py::AuditVirtual.test_remove_skips_headless_output_when_prefs_are_missing`

### 7. Medium: falsy display-virtual.json silently switches to physical panel resize

- File:line: `lib/beam_virtual.py:25-26`, `lib/beam_display.py:361-362`
- Trigger: `display-virtual.json` is `[]`, `null`, `0`, `false`, or `""` (type-confused but valid JSON). Start a stream.
- Impact: `enabled()` is `False`, so `start()` uses `choose_mode` on the real monitor and will change the 5120x1440 panel (for example to 1024x768 for a 2048x1536 request) even if `BEAM-IPAD` is still present.
- Minimal fix: `enabled()` must be a dict with `entry` and `output`. Any other JSON should be a DisplayError, not a physical modeset.
- Tests: `test_falsy_virtual_prefs_resize_the_physical_panel`, `test_json_array_session_does_not_restore_and_physical_start_crashes` (related: `load()` of `[1]` makes `start()` raise `AttributeError` instead of DisplayError)

### 8. Medium: display status fallback hides native sizing after a corrupt session file

- File:line: `lib/beam_display.py:221-223` and `261-264`
- Trigger: `display-session.json` is `null` or a non-dict while `display-virtual.json` and the iPad pin are valid.
- Impact: The except path omits `nativeResolution` and forces `ipadProfile=""`. QML treats native as false (`Service.qml:56`), so "Use this size" stays disabled and the picker says setup is unfinished. `load()` does not type-check (`lib/beam_display.py:27-29`).
- Minimal fix: Type-check `load()` to a dict. In the fallback, still report `nativeResolution=virtual.enabled()` and the saved `ipadProfile` when those files are readable.
- Tests: `test_corrupt_session_hides_native_resolution_from_status`, `test_load_null_session_is_not_an_empty_dict`

### 9. Medium: fallback_status omits the offline iPad catalog

- File:line: `lib/beam.py:739-749`
- Trigger: Any uncaught exception in `status()` (findings 3 and 7's AttributeError path). `main` returns this object with exit 0.
- Impact: No `ipadProfiles`, `nativeResolution`, `ipadProfile`, or `moonlightSetting`. The picker shows "Waiting for the screen-size catalog" even though `lib/ipads.json` is static and local.
- Minimal fix: Include `ipadProfiles=profiles()`, `nativeResolution=False`, `ipadProfile=""`, `moonlightSetting="Full"` in the fallback.
- Test: `audit_tests/test_audit_adversarial.py::AuditBackend.test_fallback_status_omits_catalog_and_native_flags`

### 10. Low: first-run welcome is one-shot and is skipped if the action lock is held

- File:line: `lib/beam.py:492-498` and `726-728`; `Service.qml:274`
- Trigger: User starts Install/Repair in the first four seconds, or any other holder of `action.lock` (non-blocking). The greet timer fires once and does not repeat. QML ignores greet failures (`Service.qml:190`).
- Impact: The required once-ever setup notification never appears, and the greeted marker is not written, but nothing retries.
- Minimal fix: Do not take `action.lock` for greet, or let QML retry greet until the helper reports the marker exists. Surface lock contention instead of a generic failure.
- Test: `audit_tests/test_audit_adversarial.py::AuditBackend.test_greet_lock_contention_does_not_write_marker` plus `AuditAstAndUi.test_service_qml_greet_is_one_shot_and_terminal_is_silent_when_busy`

### 11. Low: busy terminal clicks fail silently

- File:line: `Service.qml:240-241`
- Trigger: Click Install/Repair/Ports/Remove while `busy` is true.
- Impact: `terminal()` returns without enqueue or `actionError`. The panel keeps the previous report. This is not a truthful error.
- Minimal fix: Call `actionError("Finish the current action before starting another.")` instead of `return`.
- Test: `audit_tests/test_audit_adversarial.py::AuditAstAndUi.test_service_qml_greet_is_one_shot_and_terminal_is_silent_when_busy`

## Plausible unconfirmed risks

These need a real compositor, a real Sunshine, or a real 1024x768 shell. They were not promoted to confirmed defects.

- **Supervisor uses `hyprctl -j monitors` without `all` for virtual sessions** (`lib/beam_display.py:422`). Virtual apply/source paths pass `all_outputs=True` when mirrors are involved. If a live headless or mirrored output is omitted from the default list, `supervise` would end the session immediately. Live notes in `docs/verification/README.md` say BEAM-IPAD was visible; not re-run here.
- **Restore mode string is `5120x1440@59.97700`, which is not in `availableModes`** (`lib/beam_display.py:294-295`). Confirmed as a string mismatch in isolation. Whether Hyprland `eval` accepts it on restore is compositor-specific. Test: `test_original_mode_string_uses_five_decimals_not_advertised_text`.
- **`adminConfigured` is HTTP `Location == "/"` on `/welcome`, not a `username` line in `sunshine.conf`.** Isolated status with `username = already-created` and no process reports `adminConfigured: false` (`lib/beam.py:432-437`, `110-120`). That matches the HTTP detector and disagrees with PRD 6.4 / CLAUDE.md. Whether Sunshine's real Location header is exactly `/` after login is unverified (no network, no Sunshine).
- **1024x768 no-scroll fit.** Production QML has no `Flickable`/`ScrollView` (prototype still has one). `geometry()` exists but was not executed in a shell. Long encoder names, six Pro rows, Remove confirmation plus a long action error were not pixel-measured here.
- **Idle workspace focus after restore** if the virtual output's active workspace is `beam-idle` (`lib/beam_virtual.py:177`). Needs Hyprland workspace focus behaviour.
- **`uwsm-app` wrapper** may leave a process name other than `sunshine`, so Repair's `pgrep -x sunshine` wait could fail. Not exercised.

## What was tested and did not fail

- Baseline 70 Python + 7 JS tests, including every catalog profile's native capture and ultrawide restore, 2732x2048 at 4/3 (2049x1536 logical), same-size reselect preserving custom scale, next-stream-only profile changes, QR-first install, failed sunshine package not calling Repair, private Admin/PIN URLs, and action-queue overflow.
- Catalog: 45 uniquely named models, 17 groups, 10 sizes, four families. `readable_scale` is 2 for every size except 1024x768 (scale 1). Offline `profiles()` strips `models`.
- Installer: cancelled `qrencode` (exit 130) does not run `omarchy-pkg-add sunshine` and does not call `repair()`. Message names the QR helper.
- Browser: loopback aliases rewrite to `https://localhost:<port>` with `--private`; userinfo and off-origin URLs stay on `/usr/bin/xdg-open`.
- Pairing parser: returns only `root`; disabled `named_devices` are not counted; credential-looking sibling keys are not in the decoded object.
- AST of `lib/beam.py`: no `getpass`, no `SUDO_ASKPASS`, sudo invoked as `sudo env PATH=/usr/bin ...` with `interactive=True` so the visible terminal owns the password.
- 4/3 custom scale on 2732x2048 still applies on the next virtual start and restores the 5120x1440 scale-1 host in the fake display.

## Coverage limitations

- No real Hyprland, Sunshine, Moonlight, iPad, UFW, or Omarchy installer script. `stock_function` was not pointed at `/usr/bin/omarchy-install-service-sunshine`.
- No QML runtime, so Law 17 fit, IdleInhibitor edges, and poll/action races inside Quickshell Process objects were not executed. Service.qml behaviour for greet and silent terminal is source-level.
- `Beam.status()` in these probes used a fake System; `main()` was not invoked because it constructs `Beam()` against the real home.
- Host `/dev/uinput` readability can still affect a full `status()` `inputReady` bit; tests did not treat that as a Beam defect.
- Audio-alongside-picture is a Sunshine/Moonlight property; this copy has no audio code path to break.

## Repro locations

- `AUDIT.md` (this file)
- `audit_tests/test_audit_adversarial.py`
- `audit_tests/service-state-audit.test.js`
