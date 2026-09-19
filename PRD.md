# Beam — PRD

**An Omarchy plugin that puts the desktop you are sitting at onto an iPad.**

| | |
|---|---|
| Plugin id | `nixfred.beam` |
| Target version | 1.0.0 |
| Builder | Astra6 (`gpt-6-astra`) |
| Author of this PRD | Larry, 2026-09-19, on gus (Omarchy 4.0.4-1) |
| Repo | [`nixfred/beam`](https://github.com/nixfred/beam) (public) |
| Licence | MIT |

Everything in this document marked **verified** was checked by running it on gus on
2026-09-19. Everything marked **unverified** has not been, and must be checked during the
build rather than assumed.

---

## 1. The problem

Streaming an Omarchy desktop to an iPad already works. Sunshine sends the picture, Moonlight
on the iPad shows it, and Omarchy ships an installer for Sunshine. What does not exist is any
path through it for a person who has not done it before.

Today that person must: know the two pieces of software are called Sunshine and Moonlight,
know Moonlight is an App Store search away among several near-namesakes, run a shell command,
survive an installer that currently dies half-finished, work out that Sunshine needs a login
they must invent, find a web page on a port they have never heard of, click past a certificate
warning, type an IP address on a touch keyboard, type a PIN back on the desktop, and then
discover that the whole thing shows a black screen because the session locked.

There is a written runbook for this (`docs/original-runbook.md`). It is accurate and it is
2,400 words. That is the evidence of the problem, not the solution to it.

**Beam replaces the runbook with a plugin.** Install it, click one dot, get a picture on an
iPad.

## 2. Who it is for

1. **The first-timer.** Has installed the plugin and knows nothing else. Must reach a working
   stream without reading anything longer than a sentence at a time. This user is the reason
   the project exists and wins every design argument.
2. **The repeat user.** Has done this before, is setting up their third machine, and wants one
   screen with everything on it and a button that does the whole job.

## 3. What it is not

- **Not a network tool.** Beam assumes the iPad can already reach this machine. It does not
  configure Wi-Fi, Tailscale, routers, VPNs or DNS, and it does not diagnose why they cannot
  see each other. If there is no address, it says so and stops.
- **Not a troubleshooter for arbitrary failure.** It detects and repairs a specific, known set
  of broken states (section 8). Anything else, it reports honestly and does not guess at.
- **Not host-aware.** Beam never asks or cares whether it is on a laptop, a desktop, a VM or a
  server with a monitor hanging off it. If there is an Omarchy session with a display and an
  address, Beam works. There must be no VM-specific, laptop-specific or GPU-specific code path
  anywhere in it.
- **Not a command-line tool.** No user-facing command, no `PATH` entry, no man page, no
  documented invocation. If a reviewer can reasonably describe the deliverable as "a script",
  it has been built wrong.
- **Not a credential holder.** It never creates, stores, transmits or reads back the Sunshine
  admin password, and it never handles a sudo password.

## 4. Verified ground truth

These facts were established by running commands on gus on 2026-09-19. Build against them.

**Plugin kinds.** The only valid values are `bar`, `bar-widget`, `menu`, `overlay`, `panel`,
`service`, and a declared kind must have its matching `entryPoints` key or the plugin is
refused (`/usr/bin/omarchy-plugin-validate`, lines 97 to 110). **verified**

**Do not use the `menu` kind.** It replaces the entire Omarchy menu rather than adding an item
to it. That is what Omalaunch does, declaring `"clonedFrom": "omarchy.menu"`. Beam must not
take over the user's menu. **verified**

**The stock Sunshine installer is broken.** `/usr/bin/omarchy-install-service-sunshine` runs
under `set -e` and calls `systemctl --user enable --now sunshine`. The current package
(`sunshine 2026.516.143833-4.1` in `extra`) ships its unit as
`app-dev.lizardbyte.app.Sunshine.service`. The old name does not exist, so the script exits
there, **before** opening the firewall, installing the admin web app, and adding the Hyprland
autostart line. Every user hits this today. **verified by reading the script and the package.**

**The installer's later steps can be reused, not reimplemented.** The script is a set of shell
functions followed by a linear body starting at the line `echo "Installing Sunshine..."`.
Sourcing everything above that line gives you `open_ufw_ports`, `install_admin_webapp` and
`enable_hyprland_autostart` to call directly. Beam must reuse these so that it opens exactly
the ports Omarchy opens and nothing wider. **verified**

**Sudo does not survive between SSH invocations without a TTY.** Priming sudo in one command
and relying on the cache in the next fails. Anything needing root must happen inside one root
call. **verified in the field, documented in the runbook.**

**A render node does not mean hardware encoding.** The runbook's step 2 says that finding
`/dev/dri/renderD128` means Sunshine will find VAAPI. On a Proxmox guest with `vga: virtio-gl`
that node is virtio-gpu (`1af4:1050`), which has no video encode engine at all, and Sunshine
falls back to `libx264`. **The only honest source is Sunshine's own log line `Found H.264
encoder: <name>`.** Never infer the encoder from the presence of a DRM device. **verified on
the `ovm` guest.**

**`qrencode` 4.1.1-4 is in `extra`.** **verified**

**Moonlight on iPadOS is `id1000551566`, "Moonlight Game Streaming" by Diego Waxemberg.**
Confirmed against the iTunes lookup API. The canonical link is
`https://apps.apple.com/app/id1000551566`. Note that the store also lists "Steam Link" and
"VoidLink" for the same search terms, which is exactly why the user must not be told to
search. **verified**

**`pgrep -c` and `grep -c` print `0` and exit non-zero when the count is zero.** A
`count=$(pgrep -c x || echo 0)` idiom therefore yields the string `"0\n0"` and every later
arithmetic test on it fails. Capture first, then default. **verified: this bug was written and
then caught by running it.**

## 5. Architecture

**What is being built is an Omarchy Quickshell plugin.** It lives in the bar. The entire user
experience is a dot in the bar and a panel that opens when you click it. There is no command
for a user to learn, nothing to type, and nothing in a terminal except the one install step
that needs a password and is deliberately shown to the human.

Inside the plugin there is a bash helper. **It is an internal implementation detail, not a
product surface.** It exists because QML is a poor place to shell out from repeatedly and
because a single source of facts keeps the bar dot and the panel honest. A user never sees it,
never runs it, and its name never appears in the interface. Do not design around it as though
it were the product, and do not add user-facing commands to it.

With that understood, one rule governs the split: **the helper owns every fact and every
action; the QML only asks and relays.** This is the pattern that made the Lamplight plugin
reliable. The bar dot and the panel can then never tell the user two different stories, and
the logic stays testable without a GUI.

```
manifest.json        kinds: service, bar-widget, panel
BarWidget.qml        the product: one dot in the bar, always visible
BeamPanel.qml        the product: the wizard and the expert screen
Service.qml          holds state, polls the helper, queues actions
QrCode.qml           renders a QR png
bin/omarchy-beam     internal helper. Every fact, every action. Prints JSON.
```

The helper ships **inside the plugin directory**, and the QML resolves its path relative to
itself. It is not installed to `~/bin`, not put on `PATH`, and not documented to users. A
hardcoded `/home/<someone>/bin/...` path works on exactly one machine, and this plugin is for
strangers.

## 6. The internal helper contract

`bin/omarchy-beam <command>`, called only by the QML. This section is normative because the
QML depends on every key, not because any of it is a user interface. Nothing here is
advertised, documented to users, or reachable except through the panel.

| Command | Does |
|---|---|
| `status` | prints the JSON below, always exit 0 |
| `doctor` | the same facts, human readable, with what to do about each failure |
| `install` | runs Omarchy's installer, then `repair` to finish what it skipped |
| `repair` | fixes any of the known broken states in section 8 |
| `ports` | reopens the firewall ports using the stock installer's own function |
| `admin` | opens the Sunshine admin page |
| `pin` | opens the admin page's PIN tab |
| `qr <text>` | writes a QR png, prints its path, caches by content |
| `hold on\|off\|auto` | holds the session awake, or gives idling back |
| `greet` | fires the one first-run notification, once ever |
| `address` | prints the address to type into Moonlight |
| `undo` | removes Sunshine and everything the plugin added |

### `status` JSON

```json
{
  "installed": false, "version": "", "running": false, "processes": 0,
  "unit": "", "unitEnabled": false,
  "ufwRules": 0, "ufwPresent": true, "autostart": false,
  "adminUp": false, "adminConfigured": false, "adminUrl": "https://localhost:47990",
  "displayFound": false,
  "encoder": "", "encoderKind": "unknown",
  "recommendedRes": "Full / Safe Area · 60 fps", "recommendedBitrate": 20,
  "pairedClients": 0, "streaming": false, "locked": false,
  "address": "100.64.0.10", "addressKind": "tailscale", "lanAddress": "192.0.2.10",
  "nextStep": 2, "ready": false
}
```

The addresses above are illustrative examples.

Definitions that are not obvious:

- `encoderKind` is `hardware` if the encoder name contains vaapi, nvenc, qsv, amf or vt;
  `software` if an encoder was found and is none of those; `unknown` if Sunshine has not said
  yet. Derived from Sunshine's log only (section 4).
- `recommendedRes` uses the Moonlight client request during a sizing session;
  before connection it directs the user to Full or Safe Area at 60 FPS.
  `recommendedBitrate` starts at 40 Mbps for hardware or 20 Mbps for software.
  The previous fixed 2560x1600/1920x1080 recommendation is superseded.
- `addressKind` is `tailscale` when the address starts `100.`, else `lan`, else `none`. Prefer
  a tailnet address: it keeps working when the iPad leaves the house.
- `streaming` is the last of `CLIENT CONNECTED` / `CLIENT DISCONNECTED` in the Sunshine log.
- `nextStep` is **the single definition of how far the user got**, so that the bar dot, the
  wizard and a notification can never disagree. It returns the lowest unfinished step:
  `2` if not installed, or ports/autostart/running incomplete; `4` if no admin login; `5` if
  nothing is paired; `6` when everything is done.

### Hard rules on the helper

- **Never handle a sudo password.** Not on a command line, not in a variable, not on stdin.
  The one command that needs root (`install`) runs in a terminal the human can see and type
  into.
- **Never touch the Sunshine admin password.** Beam detects only that a `username` line exists
  in `sunshine.conf`. It never reads, sets or transmits the password.
- **`status` must be cheap.** It runs every two seconds while a stream is live. Tail the log,
  do not read it whole.
- **`status` must never fail.** Missing files, missing `ufw`, missing `tailscale`, Sunshine not
  installed: all are normal states with a JSON answer, not errors.

### 6.4 Detection recipes

These are the exact mechanics. They were established by running them; do not substitute
something that looks equivalent without testing it.

**Installed / running / count.** `command -v sunshine`, `pgrep -x sunshine`, and for the count
`n=$(pgrep -cx sunshine 2>/dev/null); printf '%s' "${n:-0}"`. Capture first: see section 4 on
why `|| echo 0` is wrong here.

**Which unit the package ships.** Probe both `app-dev.lizardbyte.app.Sunshine.service` and
`sunshine.service` against `systemctl --user list-unit-files`; empty means the package provides
no user unit and the Hyprland autostart line is the only launcher.

**Firewall rules.** Count lines matching the comment `omarchy-sunshine` in
`sudo -n ufw status`. Use `-n`: a status check must never block on a password prompt. No `ufw`
at all is a valid state, not a failure.

**Autostart.** Repair migrates the stock `o.launch_on_start("sunshine")` line to
a marked launcher in Beam's private state directory, preserving other startup
commands and saving the original file. Readiness checks the managed line, helper
contents and the running process's recorded PID/start-time identity. The launcher scopes an
`xdg-open` override to Sunshine so its pairing notification uses the same private
browser session as Beam's buttons. Only local Sunshine HTTPS pages are routed;
other links use the standard opener, and global browser preferences are untouched.
Removal deletes the managed startup line. The standalone helper survives removal
of the panel plugin itself.

**Admin login exists.** A `username` line with a non-empty value in
`~/.config/sunshine/sunshine.conf`. Never read the password field.

**Paired clients.** Count objects carrying a `uniqueid` in
`~/.config/sunshine/sunshine_state.json`. Guard the result: if it is not all digits, it is 0.

**Encoder.** `grep -aoiE 'Found H\.?264 encoder: *[a-z0-9_]+' ~/.config/sunshine/sunshine.log |
tail -1`, then strip to the name. This is the only permitted source (section 4).

**Display captured.** `Found display` or `Found monitor` anywhere in the same log.

**Streaming now.** The last line matching `CLIENT (CONNECTED|DISCONNECTED)` in the log, and it
counts as streaming only if it is the CONNECTED one. Tail the log; this runs every two seconds.

**Address.** `tailscale ip -4 | head -1` if Tailscale is present, else the `src` field of
`ip -4 route get 1.1.1.1`. Prefer the tailnet address.

**Session locked.** `pgrep -x hyprlock`, or `hyprlock` present in `hyprctl -j clients`.

**Reusing the stock installer's functions.** Find the line number of the literal line
`echo "Installing Sunshine..."` in `/usr/bin/omarchy-install-service-sunshine`, write
everything above it to a temp file, append a call to the function you want
(`open_ufw_ports`, `install_admin_webapp`, `enable_hyprland_autostart`), and run it. The
firewall one needs root: run it as **one** root call, because the script's inner `sudo ufw`
lines then need no further authentication, and because sudo caching does not survive between
invocations without a TTY (section 4).

## 7. The user experience

### 7.1 Discovery: the part that actually matters

A person installs the plugin and is told nothing. Solving that is the product. Three things,
all required:

1. **The bar dot is visible from the moment the plugin is enabled**, greyed, labelled `set up`.
   It is not hidden until configured. A widget that appears only once you have finished setting
   it up cannot help you set it up.
2. **One notification, once, ever**, four seconds after first load, and only if nothing is set
   up: *"Beam is ready to set up — Click the Beam dot in your bar to stream this desktop to
   your iPad."* The marker lives in the helper's state dir so it cannot fire twice. Per house
   rules a notification must not steal focus, and clicking it must take you there.
3. **The wizard opens on the first unfinished step**, not always at step 1. Someone who paired
   an iPad yesterday and opens Beam today lands on the last screen, not a tour.

### 7.2 Guided mode: six steps, one thing each

The step rail across the top is clickable in both directions, with a tick on finished steps. A
wizard that will not let you go back and look at something is a wizard people fight with.

| # | Title | Shows | Done when |
|---|---|---|---|
| 1 | What you need | What Sunshine and Moonlight are, in three cards: an iPad, a few minutes, your password once in a terminal | user clicks Next |
| 2 | This computer | One button that opens a terminal and installs. Five live checks: installed, ports, autostart, running, screen captured. Then an encoder card quoting Sunshine's own log and the settings that follow from it | all five checks green |
| 3 | The iPad app | **A QR code to the App Store page.** The user points the camera. Names Diego Waxemberg so the right app is unmistakable | user clicks Next |
| 4 | Your login | A button that opens the admin page. Says plainly that the user invents this password, that Beam cannot see or recover it, and that the certificate warning is expected | `adminConfigured` |
| 5 | Connect | **A QR code of this machine's address**, plus the address in large monospace. Four numbered steps. A button to the PIN page. A line saying whether this address travels or stops at the front door | `pairedClients > 0` |
| 6 | Watch | Confirmation, plus three cards: the settings to use, that Moonlight sends Cmd as Super, and that Beam holds the session awake | — |

**The two QR codes are the single biggest usability win in the product.** They remove the two
worst moments: searching an app store full of near-namesakes, and typing an IP address on a
touch keyboard. QR codes must render on a **white background with a white quiet zone in every
theme.** A themed QR on a dark panel is one a phone camera silently refuses to read, and the
user has no way to find out why.

### 7.3 Expert mode

One toggle in the header. Two dense columns, everything visible at once:

- **Left: state.** Twelve rows, each a dot plus key plus value: Sunshine, processes, firewall,
  autostart, unit, display, encoder, admin, paired, streaming, address, LAN.
- **Right: do it.** Six buttons (Install, Repair, Ports, Admin, PIN page, Remove), then a
  compact action report showing current progress, the result, and any actionable error in
  full. Remove asks first and names exactly what it destroys, including that paired iPads
  will need pairing again.

### 7.4 Law 17: nothing scrolls

**User clarification, 2026-09-19: a plugin must never require scrolling to see its
information.** This applies to both modes and to every subsection, including action results.
There is no log-box exception. Do not put a `Flickable` or `ScrollView` around plugin content.
Guided mode keeps its explicit setup steps, each fitting completely on a fixed-height stage.
Expert mode shows every status row, control and action result together in grouped columns.
Width and a better arrangement are the remedies for overflow.

Use a concise action report instead of a scrolling terminal transcript. A bounded diagnostic
history may be retained separately for troubleshooting, but an error and its recovery action
must be readable in the panel without opening that history. Do not silently clip or elide
required information, hide overflow behind tabs, or shrink text until it is unreadable.

Verify at the real usable screen size and screenshot both modes, including long errors and
the Remove confirmation. Check every edge. Also verify at 1280x800 logical resolution so a
layout that fits the host's ultrawide monitor is not mistaken for a portable layout.

### 7.5 Visual references from the running host

The live Lamplight, Burn Bar, Tesla, Detailed Weather and Chronos panels were inspected on
2026-09-19. Their shared vocabulary is theme-derived colors, thin borders, modest rounded
corners, compact typography, grouped information and meaningful status animation. Lamplight
is the control-layout reference; Burn Bar and Tesla are the dense information references.
Follow the [host style notes](docs/style-reference.md). Screenshots establish the look on
this host, not small-screen acceptance for Beam.

## 8. Known broken states Beam must own

This section is most of the engineering value. Each is a real state a user lands in.

| State | How to detect | What Beam does |
|---|---|---|
| Stock installer died half-way | installed, but ports/autostart/running incomplete | `repair` finishes the remaining steps using the installer's own functions |
| Two Sunshines on one display | `processes > 1`, or unit enabled **and** autostart line present | `repair` disables the packaged unit, leaving the autostart line as the single launcher |
| Session locks mid-stream, iPad goes black | `streaming && locked` | Hold the session awake **on the transition into streaming**, release on the transition out |
| Encoder assumed from a DRM node | n/a | Only ever read Sunshine's log, and show the user what it literally said |
| No address at all | `addressKind == "none"` | Say so on step 5 and stop. Do not attempt networking |

**The awake-hold is the highest-value single feature in this plugin.** A black screen is the
first row of every Sunshine troubleshooting table ever written, and it is not a Sunshine bug:
the compositor deliberately keeps lock surfaces out of screen capture. Holding the session
awake for exactly as long as an iPad is connected removes the entire class.

Implement it as an **edge trigger, not a level check.** Acting on the level would run two
processes a second for as long as someone watches a film. The hold must be released when
streaming stops, and the state marker must survive a shell restart so idling is never left
permanently disabled.

## 9. QML gotchas that will cost a day each

Every one of these has already bitten this codebase or a sibling plugin. They are not
suggestions.

- **`WidgetButton` has no `contentItem`.** Children go in directly, and `hasVisualContent:
  true` is what tells it something is there despite an empty label.
- **Pointer handlers do not fire reliably inside these panels.** Use `MouseArea`.
- **`Rectangle.border.width` defaults to 1 even when never set.** Pin it to 0 or you get
  hairlines everywhere.
- **Never mutate a QML `var` array in place.** `pending.shift()` returns the item but leaves
  the property holding the original array, so a queue never empties and every action re-runs
  forever. Reassign with `slice()`.
- **Never name a panel file `Panel.qml`** — it collides with the shell's own type.
- **Panel content must nest inside `KeyboardPanel`**, with `PanelKeyCatcher` handling close.
- **A `Slider`'s `value:` binding is destroyed for good by the first drag.** If any slider is
  added later, use a `Binding` gated on `pressed`.
- **Bound diagnostic history.** Retain at most ~200 lines in memory. The panel presents a
  complete, concise action report, not a scrolling history. An unbounded string on a
  long-lived shell is a slow leak.
- **Do not blur a bar widget.** A blur repaints every frame. A scaled circle at low opacity
  costs nothing and looks the same at 18px.

## 10. Acceptance criteria

Beam 1.0 ships when all of these pass **on a machine where Sunshine was never installed.**

1. `omarchy-plugin-validate` passes.
2. With Sunshine absent, `status` returns valid JSON with `nextStep: 2`, exit 0. Verify with
   `jq -e`.
3. With Sunshine absent, `doctor` runs clean with no shell errors and no `arithmetic syntax
   error`.
4. Enabling the plugin shows a grey dot labelled `set up`, and fires exactly one notification.
   Enabling it a second time fires none.
5. Clicking the dot opens the wizard on step 2, not step 1.
6. Step 2's button opens a visible terminal. The install completes **despite** the stock
   installer's unit bug, and all five checks go green without the user typing another command.
7. After install, `processes` is exactly 1. Not 0, not 2.
8. The encoder card quotes the string from Sunshine's log, and the recommendation matches it.
9. Both QR codes render, and both are readable by a phone camera **in a dark theme and a light
   theme.**
10. Completing step 4 flips `adminConfigured` without Beam ever seeing the password.
11. Pairing an iPad flips the step 5 check and auto-advances the wizard to step 6.
12. Starting a stream turns the bar dot to the accent colour and pulses it. Stopping returns it.
13. With `holdAwake` on, starting a stream holds the session awake; stopping it gives idling
    back. Confirm with `omarchy toggle idle status` on both sides of the transition.
14. All information and controls fit without scrolling, clipping or unreadable text in both
    modes, on the host and at 1280x800 logical resolution. Include long errors and the Remove
    confirmation. Screenshot both modes and inspect every edge; no log-box exception.
15. `undo` leaves `pgrep sunshine` empty and zero `omarchy-sunshine` ufw rules.
16. No `/home/pi` or any other user-specific path appears anywhere in the plugin.

## 11. Out of scope for 1.0, worth doing later

- Submitting the PIN from inside the panel instead of deep-linking to the admin page.
  **Unverified whether Sunshine's API allows this without holding the admin credentials.** If
  it costs storing the user's password, it is not worth it and the deep link stays.
- Per-client history, bandwidth graphs, multiple paired devices managed from the panel.
- Android and other Moonlight clients. The QR codes and copy are iPad-specific in 1.0.

## 12. Companion work, tracked separately

The stock installer bug (section 4) is upstream Omarchy, not ours, and every Omarchy user hits
it. It gets its own PR against Omarchy that fixes the unit name, independent of this plugin.
Beam still ships its repair path regardless, because users will be on unpatched versions for
months.

## 13. The prototype in this repo

`prototype/` holds a working first cut written while this PRD was being drafted: the helper,
four QML files and the manifest. It was removed at one point and then restored on request, so
it is here on purpose.

**Its status is reference, not gospel, and the PRD still wins wherever they disagree.** The
build called for is a clean one from this spec: read the prototype to see how something was
done, do not copy it wholesale.

The two halves are not equally trustworthy:

- **The helper, `prototype/bin/omarchy-beam`, has been run.** Its JSON validates under `jq -e`, `doctor`
  runs clean, and a real bug was found and fixed in it by executing it (the `pgrep -c` issue
  in section 4). Everything it proved is also written down in sections 4, 6 and 6.4, so the
  spec stands alone without it.
- **The QML has never been loaded into a shell.** It is a sketch of the layout and nothing
  more. Treat every line of it as unverified.
