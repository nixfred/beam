# Kimi3 and Grok bug audit

Both requested models independently audited exported copies of commit `99ee8b5`.
They ran the original 70 Python and seven JavaScript checks, then wrote and ran
their own adversarial probes. Neither auditor changed production files or operated
the live desktop. Runtime files in both copies were compared against the baseline.

| Auditor | Actual model | Additional checks | Original report |
| --- | --- | --- | --- |
| Kimi3 | `kimi-code-plan-global/k3` through OpenCode | 39 Python + 6 JavaScript | [Kimi3 report](kimi3/AUDIT.md) |
| Grok | `grok-4.6` through the Grok CLI | 28 Python + 5 JavaScript | [Grok report](grok/AUDIT.md) |

The primary engineer reviewed the findings, independently replayed both probe sets,
and verified fixes with new regressions plus real Qt and Hyprland checks. Original
reports are retained as historical evidence; their severity, causal explanations
and suggested fixes are not automatically endorsed.

## Reviewed findings

| Finding | Source | Disposition |
| --- | --- | --- |
| Capture-output loss discards recovery before restoring the physical position | Grok 1; primary VM probe | Fixed. Real Hyprland cleared `mirrorOf` but left the physical output at Beam's staging position. Recovery recognizes that exact saved geometry, restores the position and retains newer manual changes. Grok's mock assumed a dangling mirror ID, so its proposed unconditional unmirror was not used. |
| Repeated connection events keep streaming true after disconnect | Grok 2 | Fixed. The latest complete connection/disconnection event wins, as specified by the PRD. Events do not contain unique client IDs and must not accumulate as a client count. The old cache schema is rebuilt. This remains a single-iPad lifecycle indicator, not a simultaneous-client census. |
| Non-object action state, bad timestamps, incomplete log facts or invalid offsets break status | Grok 3 | Fixed. Transient state is type-checked; damaged log caches rebuild from bounded current-process evidence. |
| Repair after moving the plugin clears the selected iPad size and scale | Grok 4 | Fixed. Updating the native launcher path preserves 2732x2048, the selected model and 4/3 scale. Only initial migration clears the old physical-mode workaround. |
| Failed virtual-output removal discards ownership and blocks reinstall | Grok 5 | Fixed. Both command success and actual disappearance are required before deleting ownership. Failure remains retryable. |
| Remove should delete a named output even without ownership | Grok 6 | Rejected as proposed. The name alone does not prove ownership. Deleting an unrelated headless output would be unsafe. Fixing finding 5 prevents Beam from creating this orphan through failed removal. Missing ownership plus an existing name is still reported as a conflict. |
| Malformed native-display preferences silently trigger physical resizing | Grok 7 | Fixed. Existing ownership must be an object with a launcher and the expected output. Invalid durable files are preserved and cause a typed error before modesetting. |
| Damaged recovery state hides a valid saved iPad profile | Grok 8 | Fixed. Status retains independently readable native/profile facts and reports the recovery error. |
| Probe fallback hides the offline iPad catalog | Grok 9 | Fixed. Fallback includes the catalog and explicit sizing defaults. |
| Setup lock consumes the once-only welcome attempt | Grok 10 | Fixed. Welcome uses its own lock, retaining once-only behavior without competing with installation. |
| Busy setup buttons silently ignore clicks | Grok 11 | Not an observable UI defect. Every relevant production button is disabled while busy; the backend guard prevents duplicate invocation. Replacing a running action's report with an extra busy error would obscure progress. |
| Saved UFW rules omit Tailscale completeness checks | Kimi3 1 | Fixed. Saved and active rules require the Tailscale permissions when that interface exists. Saved tuple syntax was checked against installed UFW source; deny rules do not satisfy readiness. |
| Invalid cached QR image cannot recover on retry | Kimi3 2 | Fixed. Invalid headers and truncated PNGs regenerate; Qt does not retain stale decoded image data. Verified with real `qrencode` and the Qt image loader. |
| Incomplete recovery object fails with a generic exception | Kimi3 3 | Fixed. Session structure is checked before start, stop, supervision or preparation. The file is preserved with a specific `display-session.json` error. Beam cannot reconstruct missing original monitor settings safely. |
| Disabled physical source produces an untyped recovery failure | Kimi3 4 | Fixed. Recovery reports the disabled/disconnected source, retains its record, and succeeds after re-enabling the source. |
| Duplicate Sunshine configuration keys disagree | Kimi3 5 | Fixed with different precedence than proposed. Sunshine uses the first key, so Beam's general reader now agrees with the existing browser reader. The reported Admin/PIN port divergence was not reproduced: both actual URL paths already use `admin_port`. Other duplicated keys such as `file_apps` could differ. |
| Timed-out Qt helper exits after the next action starts | Primary native Qt probe | Fixed. A timed-out process retains ownership until its exit is acknowledged; late output is ignored, and an unresponsive helper is killed after two seconds. Polls use the same retirement guard. |
| Interrupted setup gets a new timestamp every poll and overwrites later action results | Primary isolated probe | Fixed. Interruption is persisted once under the action lock. Reopening a dead action works without an intervening poll and cannot overwrite another lock owner. |
| Selecting the idle workspace leaves focus on the parked output after disconnect | Both models' unconfirmed risks; primary VM probe | Confirmed and fixed. Recovery excludes `beam-idle` from its focus target and returns to the saved source workspace. The real compositor reproduced the failure and verified the fix. |

Sunshine's [matching-release config parser](https://github.com/LizardByte/Sunshine/blob/v2026.516.143833/src/config.cpp)
uses first-key insertion. Its [connection event logging](https://github.com/LizardByte/Sunshine/blob/v2026.516.143833/src/stream.cpp)
was inspected when reviewing the lifecycle finding. The stale credential-detection
description in `PRD.md` and `CLAUDE.md` now matches Beam's existing unauthenticated
loopback `/welcome` probe.

## Verification

- Current regression suite: **96 Python + 7 JavaScript checks**, including real
  offscreen Qt tests for delayed exits, ignored termination and QR recovery.
  Native tests skip explicitly when Quickshell or qrencode is unavailable; all
  native tests ran here.
- The expanded suite was replayed against the old production code. It reproduced
  failures, including both native timeout races and the native QR cache failure.
  The original auditors' probes deliberately assert baseline bugs and are separate
  from the current regression suite.
- In the isolated Omarchy VM, removing BEAM-IPAD during a synthetic stream used
  to leave the physical monitor at x=5632 instead of its saved x=6656 while
  reporting success. With the fix it returned to x=6656. Capture-output removal
  and recreation then both passed with the original VM layout restored.
- A rotated VM output retained transform 1 when a non-mirror mode update omitted
  the transform field. That concern did not reproduce on the tested compositor.
  Restoring focus from `beam-idle` did fail, then passed with the fix.
- All 17 iPad profiles, exact native sizing, custom 4/3 scale preservation,
  superseded-session tokens and manual-layout preservation remain covered.
- Final host verification caught and corrected an overly strict UFW parser assumption in the initial patch: inbound rules may show `ALLOW` without `IN`. A regression now covers both inbound forms, `DENY` and `ALLOW OUT`. No firewall rules were changed; actual readiness returned to true.
- Manifest validation and whitespace checks pass. This change does not alter
  panel geometry; prior 1024x768 dark/light no-scroll evidence remains in the
  [verification report](../../verification/README.md).

## Replay the independent audits

Run from a complete checkout containing baseline commit `99ee8b5`:

```sh
python docs/audits/2026-09-19/replay.py kimi3
python docs/audits/2026-09-19/replay.py grok
```

The runner exports the old commit into a temporary directory and copies only the
chosen auditor's tests there. Tests use fake systems and temporary homes. Running
these historical probes against the fixed source would fail because their bug
assertions describe the old behavior.

Current checks:

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
node tests/service-state.test.js
omarchy-plugin-validate .
git diff --check
```

## Physical acceptance limits

These audits did not initiate a new physical iPad stream. Earlier user acceptance
confirmed pairing, picture, sound/music and matching 2732x2048 capture; subsequent
host readback confirmed 5120x1440 at scale 1 with mirroring off. Camera scanning,
input quality, Full/Safe Area requests and other iPad models still need physical
acceptance. Neither model's mocked checks establish those results.
