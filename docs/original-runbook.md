# Remote desktop from an iPad to `ovm` over Tailscale

Audience: an AI agent (Claude Code, or Larry) doing the setup, and the human who owns the
devices. The agent does every step marked **AGENT**. Steps marked **HUMAN** create credentials
or approve access, so the agent must hand them to the human and wait.

Stack: **Sunshine** (streaming host) on `ovm`, **Moonlight** (client) on the iPad, both on the
same tailnet. Written from a working install on a bare-metal Omarchy box on 2026-09-18. The VM
specifics in step 2 are not yet proven on `ovm`, so check them rather than assuming.

## Rules for the agent

- Never create the Sunshine admin login, choose its password, or type any password into a lock
  screen or login prompt. Hand those steps to the human.
- Never widen firewall rules beyond what the Omarchy installer opens (private LAN ranges and
  `tailscale0`). Never expose ports to the internet.
- Pass any sudo password on stdin (`sudo -S`), never on a command line, in a file, or in an
  exported variable.
- Verify each step with the check listed under it before going on. If a check fails, stop and
  report the exact output.

## 0. Preconditions

**AGENT**, on `ovm` over SSH:

```bash
tailscale status --self          # ovm is online in the tailnet
tailscale ip -4                  # note this 100.x address, the iPad connects to it
command -v omarchy               # present means ovm runs Omarchy, so use step 3
echo "$XDG_SESSION_TYPE"         # expect wayland once a graphical session is running
```

Check: `ovm` is online and has a 100.x address. If `omarchy` is missing, `ovm` is not an Omarchy
install. Stop and ask the human before improvising, because step 3 assumes Omarchy's installer.

**HUMAN**, on the iPad:

- Install **Tailscale** and sign in to the same tailnet. Confirm `ovm` shows in the device list.
- Install **Moonlight** from the App Store.

## 1. A graphical session must exist and be unlocked

Sunshine streams a real display. It has nothing to show on a VM with no session, and on a locked
Hyprland session it does not show the lock screen (the compositor keeps lock surfaces out of
screen capture). The human has to unlock it: do not script a password into the lock screen.

**AGENT**:

```bash
export OMARCHY_PATH=/usr/share/omarchy
omarchy toggle idle status        # "enabled":true means stay-awake is on
omarchy toggle idle stay-awake    # keep the session from idling back into the lock
omarchy system wake               # a powered-off display makes capture hang
```

Over non-interactive SSH, `omarchy` subcommands need `OMARCHY_PATH` set, and display commands
need the session's `WAYLAND_DISPLAY`, `XDG_RUNTIME_DIR` and `HYPRLAND_INSTANCE_SIGNATURE`. Read
them from the running session (for example from `/proc/<pid>/environ` of the running Hyprland)
rather than guessing.

**HUMAN**: unlock the session once, at the VM console or through the hypervisor's own viewer.

## 2. Check whether the VM can encode video

**AGENT**:

```bash
ls /dev/dri/ 2>/dev/null          # renderD128 means a GPU device is passed through
```

- With a render node, Sunshine should find hardware encoders (VAAPI).
- Without one, which is common in a VM, Sunshine falls back to software H.264 (`libx264`). That
  works but costs CPU. Give `ovm` at least 4 vCPUs and plan to lower the Moonlight resolution
  (step 6).

The result is confirmed in step 4 from Sunshine's own log.

## 3. Install Sunshine the Omarchy way

**AGENT**:

```bash
omarchy install service sunshine
```

That stock installer installs the package, opens Moonlight's ports for private LANs and
`tailscale0` through `ufw`, adds a "Sunshine Admin" web app, and adds
`o.launch_on_start("sunshine")` to `~/.config/hypr/autostart.lua`.

**Known failure (seen 2026-09-18, sunshine 2026.516.143833):** the installer runs under `set -e`
and calls `systemctl --user enable --now sunshine`, but the package now ships its unit as
`app-dev.lizardbyte.app.Sunshine.service`. The script then stops with
`Unit sunshine.service does not exist` before the firewall, web app and autostart steps. Check:

```bash
systemctl --user list-unit-files | grep -i sunshine
```

If the unit has the long name and the script stopped, finish the remaining steps with the
script's own functions instead of hand-written rules:

```bash
src=/usr/bin/omarchy-install-service-sunshine
n=$(grep -nxF 'echo "Installing Sunshine..."' "$src" | cut -d: -f1)
d=$(mktemp -d)
{ head -n $((n-1)) "$src"; echo open_ufw_ports; } > "$d/ufw.sh"
{ head -n $((n-1)) "$src"; echo install_admin_webapp; echo enable_hyprland_autostart; } > "$d/user.sh"
chmod 0755 "$d"; chmod 0644 "$d"/*.sh
# One sudo for the whole firewall step: as root, the script's inner "sudo ufw" calls need no password.
printf '%s\n' "$SUDO_PASSWORD_FROM_A_SECRET_STORE" | sudo -S -k -p "" env PATH=/usr/bin bash "$d/ufw.sh"
bash "$d/user.sh"
rm -rf -- "$d"
setsid -f uwsm-app -- sunshine >/dev/null 2>&1 </dev/null   # start it now the way autostart will
```

Priming sudo once and running the script in a subshell does **not** work over SSH without a
TTY: the cached authentication does not carry over. The one-root-call pattern above does.

Leave the renamed systemd unit **disabled**. Together with the Hyprland autostart line it would
start a second Sunshine, and `omarchy remove service sunshine` only knows the old unit name.

Checks:

```bash
pgrep -a sunshine                                  # exactly one process
sudo ufw status | grep -c omarchy-sunshine         # non-zero
tail -2 ~/.config/hypr/autostart.lua               # ends with o.launch_on_start("sunshine")
```

## 4. Confirm Sunshine found the display and an encoder

**AGENT**:

```bash
grep -iE 'Found display|Found monitor|Found H.264|Found HEVC|Error' ~/.config/sunshine/sunshine.log | tail -15
```

Expect `[wayland] Found display`, a `Found monitor` line, and `Found H.264 encoder: ...`.
Errors about `av1_vaapi` are harmless on hardware without AV1 encode; Sunshine says to ignore
them. If no H.264 encoder is found at all, stop and report the log lines.

From another tailnet device, check the port answers:

```bash
nc -z -G 3 <ovm-100.x-address> 47989 && echo reachable
```

## 5. Admin login and pairing (HUMAN, agent guides)

Sunshine's admin page trusts only local and LAN origins, so reach it through an SSH tunnel.

**HUMAN**, from a computer on the tailnet:

```bash
ssh -N -L 47990:localhost:47990 <user>@ovm
```

Open `https://localhost:47990`, accept the self-signed certificate, and **create the admin
username and password**. The agent must not do this step.

**HUMAN**, on the iPad:

1. Moonlight, tap **+**, enter the `ovm` Tailscale address (100.x). Moonlight shows a 4-digit PIN.
2. On the Sunshine admin page, open the **PIN** tab, enter the PIN, name the device, press Send.
3. Tap `ovm` in Moonlight, then **Desktop**.

**AGENT** checks pairing and the stream from the log:

```bash
grep -iE 'streaming session started|CLIENT CONNECTED|Selected monitor|bitrate' ~/.config/sunshine/sunshine.log | tail -6
```

Expect `New streaming session started` and `CLIENT CONNECTED`.

## 6. iPad usage notes

- **Desktop** streams the whole screen. The other entries launch single apps.
- With a keyboard attached, Moonlight forwards the Cmd key as Super, which Omarchy uses for most
  shortcuts. If Cmd shortcuts are swallowed by iPadOS, look in Moonlight's settings for the
  option that captures system keyboard shortcuts.
- On a software encoder (step 2), set Moonlight's resolution to 1080p and 30 or 60 fps if the
  stream stutters.
- End the stream from Moonlight's in-stream menu. Quitting the app does too.

## 7. Undo

**AGENT**:

```bash
omarchy remove service sunshine        # package, ufw rules, autostart line, admin web app
omarchy toggle idle allow-idle         # let the session idle and lock again
```

Check `pgrep sunshine` is empty and `sudo ufw status | grep -c omarchy-sunshine` prints 0.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Stream is black or shows only the wallpaper | Session locked | HUMAN unlocks; AGENT turns stay-awake on |
| Screen capture hangs | Display is powered off | `omarchy system wake` |
| `Unit sunshine.service does not exist` | Upstream renamed the unit | Step 3, known failure |
| `sudo: a terminal is required` | Sudo cached in one process, used in another | One root call, step 3 |
| Admin page refuses to load over 100.x | Web UI trusts LAN and localhost only | SSH tunnel, step 5 |
| High CPU, choppy video | Software encoding in the VM | GPU passthrough, or lower resolution |
| Tailscale SSH asks for a browser check every 12 h | Policy `"action": "check"` | Fixed 12 h on the Free plan; use normal SSH with a key over a LAN route, or `"accept"` if every tailnet device is trusted |
