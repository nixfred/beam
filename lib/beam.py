#!/usr/bin/env python3
"""Beam's private backend. No passwords, remote administration or network repair."""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import signal
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from beam_display import DisplayError, DisplayFit
from beam_browser import BrowserBridge, admin_port

APP_STORE = "https://apps.apple.com/app/id1000551566"
UNITS = ("app-dev.lizardbyte.app.Sunshine.service", "sunshine.service")
PRIVILEGED = {"install", "repair", "ports", "undo"}
PORTS = {"tcp": (47984, 47989, 48010), "udp": (5353, 47998, 47999, 48000, 48002, 48010)}
PRIVATE_CIDRS = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")


def result(ok, action, message, detail="", retry="", **extra):
    return dict(ok=ok, action=action, message=message, detail=detail,
                retryAction=retry, **extra)


def read_text(path, limit=262144):
    try:
        with Path(path).open(errors="replace") as stream:
            return stream.read(limit)
    except OSError:
        return ""


def read_json(path, fallback=None):
    try:
        return json.loads(read_text(path))
    except (ValueError, TypeError):
        return {} if fallback is None else fallback


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".beam-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, ensure_ascii=False)
            stream.write("\n")
        os.replace(name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(name)


class Failure(Exception):
    def __init__(self, message, detail="", retry="repair"):
        self.message, self.detail, self.retry = message, detail, retry


class System:
    """The only OS boundary. Tests inject this without changing the host."""
    def have(self, name):
        return bool(shutil.which(name))

    def run(self, args, timeout=2, interactive=False):
        try:
            done = subprocess.run(args, text=True, timeout=timeout,
                                  stdin=None if interactive else subprocess.DEVNULL,
                                  stdout=None if interactive else subprocess.PIPE,
                                  stderr=None if interactive else subprocess.DEVNULL)
            return done.returncode, done.stdout or ""
        except subprocess.TimeoutExpired:
            return 124, ""
        except OSError:
            return 127, ""

    def spawn(self, args, output=None):
        child = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                                 stdout=output or subprocess.DEVNULL,
                                 stderr=output or subprocess.DEVNULL,
                                 start_new_session=True)
        # The setup terminal can stay open at its final prompt. Reap children
        # that exit meanwhile instead of leaving Sunshine as a zombie there.
        threading.Thread(target=child.wait, daemon=True).start()
        return child.pid

    def copy(self, text):
        try:
            return subprocess.run(["wl-copy", "--type", "text/plain;charset=utf-8"],
                                  input=text, text=True, timeout=2,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def admin(self, port):
        # Self-signed HTTPS is expected, ONLY on numeric loopback, no proxy or
        # redirect following, no Authorization header, and no response body read.
        connection = http.client.HTTPSConnection(
            "127.0.0.1", port, timeout=0.7, context=ssl._create_unverified_context())
        try:
            connection.request("GET", "/welcome")
            response = connection.getresponse()
            configured = response.status in (301, 302, 303, 307, 308) and response.getheader("Location") == "/"
            known = configured or response.status == 200
            return True, configured, known
        except (OSError, http.client.HTTPException):
            return False, False, False
        finally:
            connection.close()


def process_identity(pid, proc=Path("/proc")):
    try:
        base = proc / str(pid)
        stat = (base / "stat").read_text()
        fields = stat[stat.rfind(")") + 2:].split()
        if fields[0] in ("Z", "X"):
            return ""
        return fields[19]
    except (OSError, IndexError):
        return ""


def pairing_root(path):
    """Read only the public pairing subtree, never decode credential values.

    Sunshine stores pairing records and the web password hash in one JSON file.
    A selective streaming parser skips top-level credential fields one character
    at a time without collecting their values. Only `root` is JSON-decoded.
    """
    try:
        if path.stat().st_size > 4 * 1024 * 1024:
            return {}
        with path.open(encoding="utf-8") as stream:
            def char():
                c = stream.read(1)
                if not c:
                    raise ValueError("incomplete JSON")
                return c

            def nonspace():
                c = char()
                while c.isspace():
                    c = char()
                return c

            def value(first, keep):
                parts = [first] if keep else []
                quoted = first == '"'
                escaped = False
                depth = 1 if first in "[{" else 0
                if not quoted and not depth:
                    c = char()
                    while c not in ",}":
                        if keep:
                            parts.append(c)
                        c = char()
                    return "".join(parts), c
                while True:
                    c = char()
                    if keep:
                        parts.append(c)
                    if quoted:
                        if escaped:
                            escaped = False
                        elif c == "\\":
                            escaped = True
                        elif c == '"':
                            quoted = False
                            if depth == 0:
                                break
                    elif c == '"':
                        quoted = True
                    elif c in "[{":
                        depth += 1
                    elif c in "]}":
                        depth -= 1
                        if depth == 0:
                            break
                return "".join(parts), None

            if nonspace() != "{":
                return {}
            c = nonspace()
            while c != "}":
                if c != '"':
                    return {}
                key, _ = value(c, True)
                if nonspace() != ":":
                    return {}
                wanted = json.loads(key) == "root"
                data, delim = value(nonspace(), wanted)
                if wanted:
                    root = json.loads(data)
                    return root if isinstance(root, dict) else {}
                c = delim or nonspace()
                if c == ",":
                    c = nonspace()
            return {}
    except (OSError, ValueError, UnicodeError):
        return {}


def paired_count(root):
    named = root.get("named_devices", [])
    if isinstance(named, list):
        return sum(isinstance(d, dict) and bool(d.get("uuid")) and bool(d.get("cert"))
                   and str(d.get("enabled", True)).lower() not in ("false", "0") for d in named)
    return 0


def legacy_paired_count(root):
    devices = root.get("devices", [])
    if not isinstance(devices, list):
        return 0
    return sum(isinstance(d, dict) and bool(d.get("uniqueid")) and bool(d.get("certs")) for d in devices)


class Beam:
    def __init__(self, home=None, system=None, proc=None, etc=None):
        self.home = Path(home or Path.home())
        self.system = system or System()
        # XDG overrides are ignored for explicitly supplied test homes.
        self.config = Path(os.getenv("XDG_CONFIG_HOME", self.home / ".config")) if home is None else self.home / ".config"
        self.state = (Path(os.getenv("XDG_STATE_HOME", self.home / ".local/state")) if home is None else self.home / ".local/state") / "omarchy/beam"
        self.cache = (Path(os.getenv("XDG_CACHE_HOME", self.home / ".cache")) if home is None else self.home / ".cache") / "omarchy/beam"
        self.sun = self.config / "sunshine"
        self.proc = Path(proc or "/proc")
        self.etc = Path(etc or "/etc")
        self.entry = Path(__file__).resolve().parent.parent / "bin/omarchy-beam"
        self.autostart = self.home / ".config/hypr/autostart.lua"
        self.browser = BrowserBridge(self.state, self.autostart)
        self.display = DisplayFit(self)

    def run(self, args, **kwargs):
        return self.system.run(args, **kwargs)

    def config_values(self):
        allowed = {"log_path", "file_state", "port", "file_apps", "output_name"}
        values = {}
        for line in read_text(self.sun / "sunshine.conf", 65536).splitlines():
            key, _, val = line.partition("=")
            if key.strip() in allowed:
                values[key.strip()] = val.strip()
        return values

    def processes(self, name="sunshine"):
        rc, output = self.run(["pgrep", "-u", str(os.getuid()), "-x", name])
        rows = []
        for word in output.split():
            if not word.isdigit():
                continue
            pid = int(word)
            base = self.proc / word
            identity = process_identity(pid, self.proc)
            if not identity:
                continue
            stat_text = read_text(base / "stat", 4096)
            if stat_text[stat_text.rfind(")") + 2:].startswith("Z "):
                continue
            try:
                environment = (base / "environ").read_bytes().split(b"\0")
                # Do not retain or report environment values other than display.
                display = next((x.partition(b"=")[2].decode(errors="replace") for x in environment if x.startswith(b"WAYLAND_DISPLAY=")), "")
                if display and os.environ.get("WAYLAND_DISPLAY") and display != os.environ["WAYLAND_DISPLAY"]:
                    continue
            except OSError:
                display = ""
            try:
                uptime = float(read_text(self.proc / "uptime", 128).split()[0])
            except (ValueError, IndexError):
                continue
            started = time.time() - uptime + int(identity) / os.sysconf("SC_CLK_TCK")
            rows.append(dict(pid=pid, identity=identity, started=started, display=display,
                             browser=name == "sunshine" and self.browser.owns_process(pid, identity)))
        return rows

    def units(self):
        rc, output = self.run(["systemctl", "--user", "list-unit-files", "--no-legend", *UNITS])
        found = []
        for line in output.splitlines():
            cells = line.split()
            if len(cells) > 1 and cells[0] in UNITS:
                found.append((cells[0], cells[1] in ("enabled", "enabled-runtime")))
        return found

    def firewall(self):
        base = dict(ufwPresent=self.system.have("ufw"), ufwRules=0,
                    firewallState="absent", firewallKnown=True, firewallReady=True)
        if not base["ufwPresent"]:
            return base
        # Never prompt in status. Read UFW's saved rules when access is allowed.
        rc, output = self.run(["sudo", "-n", "ufw", "status"], timeout=1)
        if rc == 0 and "Status: inactive" in output:
            return dict(base, firewallState="inactive")
        entries = []
        if rc == 0 and "Status: active" in output:
            for line in output.splitlines():
                if "# omarchy-sunshine" in line:
                    entries.append(line)
            expected = [(str(p) + "/" + proto, cidr) for proto, ports in PORTS.items() for p in ports for cidr in PRIVATE_CIDRS]
            complete = all(any(port in e.split() and cidr in e.split() and "ALLOW" in e for e in entries) for port, cidr in expected)
            if (self.etc.parent / "sys/class/net/tailscale0").exists():
                complete = complete and all(any(str(p) + "/" + proto in e.split() and "tailscale0" in e for e in entries) for proto, ports in PORTS.items() for p in ports)
            return dict(base, ufwRules=len(entries), firewallState="open" if complete else "incomplete", firewallReady=complete)
        rule_file = self.etc / "ufw/user.rules"
        saved = read_text(rule_file)
        if saved:
            marker = "omarchy-sunshine".encode().hex()
            entries = [line.split() for line in saved.splitlines() if line.startswith("### tuple ###") and "comment=" + marker in line]
            complete = all(any(len(e) > 10 and e[3:6] == ["allow", proto, str(p)] and e[8] == cidr and e[9] == "in" for e in entries) for proto, ports in PORTS.items() for p in ports for cidr in PRIVATE_CIDRS)
            return dict(base, ufwRules=len(entries), firewallState="configured" if complete else "incomplete", firewallReady=complete)
        return dict(base, firewallState="unknown", firewallKnown=False, firewallReady=False)

    def addresses(self, paired=True):
        _, route = self.run(["ip", "-j", "-4", "route", "get", "1.1.1.1"])
        lan = ""
        try:
            lan = str(ipaddress.IPv4Address(json.loads(route)[0].get("prefsrc", "")))
        except (ValueError, IndexError, KeyError, TypeError):
            pass
        ts = ""
        if self.system.have("tailscale"):
            rc, output = self.run(["tailscale", "ip", "-4"], timeout=1)
            if rc == 0:
                try:
                    ts = str(ipaddress.IPv4Address(output.splitlines()[0].strip()))
                except (ValueError, IndexError):
                    pass
        chosen = (ts or lan) if paired else (lan or ts)
        return dict(address=chosen, addressKind="tailscale" if chosen and chosen == ts else "lan" if chosen else "none", lanAddress=lan, tailscaleAddress=ts)

    def log_facts(self, processes, path):
        empty = dict(encoder="", displayFound=False, streaming=False, streamCount=0, logCurrent=False)
        if len(processes) != 1:
            return empty
        current = processes[0]
        identity = str(current["pid"]) + ":" + current["identity"]
        previous = read_json(self.cache / "log.json")
        try:
            stat = path.stat()
            same = previous.get("process") == identity and previous.get("inode") == stat.st_ino and previous.get("offset", 0) <= stat.st_size
            facts = dict(previous.get("facts", empty)) if same else dict(empty)
            offset = previous.get("offset", 0) if same else 0
            # Bounded bootstrap and bounded incremental reads. If the log gets too
            # far ahead, evidence becomes unknown instead of carrying stale state.
            skipped = False
            if stat.st_size - offset > 262144:
                offset = max(0, stat.st_size - 262144)
                facts = dict(empty)
                skipped = True
            with path.open("rb") as stream:
                stream.seek(offset)
                data = stream.read(262144)
            discarded = 0
            if offset and (not same or skipped):
                first, delim, rest = data.partition(b"\n")
                discarded = len(first) + len(delim)
                data = rest
            # Do not advance across a half-written line.
            consumed = data.rfind(b"\n") + 1
            lines = data[:consumed].decode(errors="replace").splitlines()
            for line in lines:
                stamp = re.match(r"\[(\d{4}[-:]\d{2}[-:]\d{2}[ T:]\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]", line)
                if not stamp:
                    continue
                normalized = stamp[1].replace(":", "-", 2) if stamp[1][4] == ":" else stamp[1]
                if normalized[10] == ":":
                    normalized = normalized[:10] + " " + normalized[11:]
                try:
                    when = dt.datetime.fromisoformat(normalized).timestamp()
                except ValueError:
                    continue
                if when < current["started"] - 2:
                    continue
                facts["logCurrent"] = True
                match = re.search(r"Found H\.?264 encoder:\s*([\w-]+)", line, re.I)
                if match:
                    facts["encoder"] = match[1]
                if re.search(r"Found (?:display|monitor)|Detected display", line, re.I):
                    facts["displayFound"] = True
                if "CLIENT CONNECTED" in line:
                    facts["streamCount"] += 1
                if "CLIENT DISCONNECTED" in line:
                    facts["streamCount"] = max(0, facts["streamCount"] - 1)
            facts["streaming"] = facts["streamCount"] > 0
            atomic_json(self.cache / "log.json", dict(process=identity, inode=stat.st_ino, offset=offset + discarded + consumed, facts=facts))
            return facts
        except (OSError, ValueError, TypeError):
            return empty

    def action_state(self):
        saved = read_json(self.state / "action.json")
        if saved.get("busy"):
            pid = saved.get("pid")
            pending = saved.get("phase") == "opening" and time.time() * 1000 - saved.get("updatedAt", 0) < 20000
            live = bool(pid and process_identity(pid, self.proc) == saved.get("identity") and saved.get("identity"))
            if not (pending or live):
                saved = result(False, saved.get("action", ""), "The setup terminal closed before finishing.", "Open the action again to continue.", saved.get("action", "repair"), id=saved.get("id", ""), state="error", busy=False, phase="interrupted", updatedAt=time.time() * 1000)
        return saved

    def status(self):
        procs = self.processes()
        values = self.config_values()
        port = admin_port(self.config)
        log = Path(values.get("log_path", "sunshine.log"))
        if not log.is_absolute():
            log = self.sun / log
        pair_file = Path(values.get("file_state", "sunshine_state.json"))
        if not pair_file.is_absolute():
            pair_file = self.sun / pair_file
        pair_root = pairing_root(pair_file)
        clients = paired_count(pair_root) + legacy_paired_count(pair_root)
        installed = self.system.have("sunshine")
        _, version = self.run(["pacman", "-Q", "sunshine"]) if installed else (0, "")
        units = self.units()
        up, configured, admin_known = self.system.admin(port) if procs else (False, False, False)
        s = dict(installed=installed, version=version.strip().removeprefix("sunshine "), running=bool(procs), processes=len(procs),
                 unit=units[0][0] if units else "", unitEnabled=any(u[1] for u in units),
                 autostart=self.browser.ready(),
                 browserReady=len(procs) == 1 and procs[0].get("browser", False),
                 adminUp=up, adminConfigured=configured, adminKnown=admin_known, adminUrl=f"https://localhost:{port}",
                 pairedClients=clients, locked=bool(self.processes("hyprlock")),
                 qrAvailable=self.system.have("qrencode"), appStoreUrl=APP_STORE,
                 inputReady=os.access("/dev/uinput", os.W_OK), lastAction=self.action_state())
        s.update(self.firewall())
        s.update(self.addresses(paired=clients > 0))
        s.update(self.log_facts(procs, log))
        rc, locked = self.run(["omarchy-shell", "lock", "isLocked"], timeout=1)
        s["locked"] = s["locked"] or (rc == 0 and locked.strip() == "true")
        s["encoderKind"] = "unknown" if not s["encoder"] else "hardware" if re.search(r"vaapi|nvenc|qsv|amf|videotoolbox", s["encoder"], re.I) else "software"
        s.update(self.display.status())
        s["recommendedBitrate"] = 40 if s["encoderKind"] == "hardware" else 20
        s["setupReady"] = all((installed, len(procs) == 1, s["autostart"], s["browserReady"], not s["unitEnabled"], s["firewallReady"], s["displayFound"], bool(s["encoder"]), up, s["inputReady"], s["resolutionReady"]))
        s["nextStep"] = 2 if not s["setupReady"] else 4 if not configured else 5 if not clients else 6
        s["ready"] = s["setupReady"] and configured and clients > 0 and bool(s["address"]) and not s["locked"]
        s["actionBusy"] = bool(s["lastAction"].get("busy"))
        s["checks"] = [dict(key=k, label=label, ok=bool(ok), state="ok" if ok else "attention") for k, label, ok in (
            ("installed", "Sunshine installed", installed), ("firewall", "Streaming ports", s["firewallReady"]),
            ("autostart", "Startup + pairing browser", s["autostart"] and s["browserReady"] and not s["unitEnabled"]),
            ("running", "One Sunshine running", len(procs) == 1), ("display", "Display + iPad sizing", s["displayFound"] and s["resolutionReady"]))]
        issues = []
        def issue(code, message, action="", detail=""):
            issues.append(dict(code=code, message=message, action=action, detail=detail))
        if not installed:
            issue("missing", "Install Sunshine on this computer.", "install")
        elif len(procs) != 1 or not s["autostart"] or not s["browserReady"] or s["unitEnabled"]:
            issue("startup", "Finish this computer's setup.", "repair")
        if installed and not s["firewallReady"]:
            issue("firewall", "Streaming ports need checking." if not s["firewallKnown"] else "Streaming ports are incomplete.", "ports")
        if procs and not s["displayFound"]:
            issue("display", "Sunshine has not confirmed a display.", "admin", "Check the Sunshine page for its capture error.")
        if installed and not s["resolutionReady"]:
            issue("resolution", "Enable automatic iPad sizing with Repair.", "repair")
        if s.get("resolutionError"):
            issue("resolution-error", s["resolutionError"], "restore-display" if s["resolutionActive"] else "", s["resolutionDetail"])
        if s["locked"]:
            issue("locked", "Unlock this computer before connecting.", "", "Beam cannot unlock your session.")
        if not s["address"]:
            issue("address", "This computer has no usable address.", "", "Beam expects an already reachable computer.")
        if not s["qrAvailable"]:
            issue("qr", "Install the QR code helper for easy iPad setup.", "install")
        if procs and not s["inputReady"]:
            issue("input", "Sunshine may not have access to mouse and keyboard input.", "admin", "Check Sunshine's input error before connecting.")
        s["issues"] = issues
        return s

    def progress(self, action, message, phase="running", **extra):
        previous = read_json(self.state / "action.json")
        data = result(True, action, message, busy=True, phase=phase, pid=os.getpid(),
                      id=previous.get("id") or uuid.uuid4().hex, state="working",
                      identity=process_identity(os.getpid(), self.proc), updatedAt=time.time() * 1000, **extra)
        atomic_json(self.state / "action.json", data)
        print(message, file=sys.stderr, flush=True)

    @contextlib.contextmanager
    def lock(self):
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.state / "action.lock").open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Failure("Another Beam action is already running.", "Finish its terminal first.", "")
            yield

    def require(self, args, message, retry="repair", timeout=60, interactive=False):
        rc, _ = self.run(args, timeout=timeout, interactive=interactive)
        if rc:
            raise Failure(message, f"The command exited with code {rc}. See the setup terminal, then retry.", retry)

    def stock_function(self, function, root=False, remove=False):
        script = Path("/usr/bin/omarchy-remove-service-sunshine" if remove else "/usr/bin/omarchy-install-service-sunshine")
        content = read_text(script)
        marker = 'systemctl --user disable --now sunshine' if remove else 'echo "Installing Sunshine..."'
        lines = content.splitlines()
        try:
            stop = next(i for i, line in enumerate(lines) if line.startswith(marker))
        except StopIteration:
            raise Failure("Omarchy's Sunshine installer changed or is missing.", "Update Beam before retrying; no replacement firewall rules were guessed.")
        prefix = "\n".join(lines[:stop])
        if not re.search(r"^" + re.escape(function) + r"\(\)\s*\{", prefix, re.M):
            raise Failure("Omarchy's Sunshine action is unavailable.", "Update Beam and Omarchy, then retry.")
        if function == "install_admin_webapp":
            prefix += f"\nSUNSHINE_ADMIN_URL=https://localhost:{admin_port(self.config)}\n"
            prefix += 'SUNSHINE_ADMIN_EXEC="omarchy-launch-browser --private $SUNSHINE_ADMIN_URL"\n'
        with tempfile.TemporaryDirectory(prefix="beam-stock-") as directory:
            path = Path(directory) / "action.sh"
            path.write_text(prefix + "\n" + function + "\n")
            args = ["bash", str(path)]
            if root:
                args = ["sudo", "env", "PATH=/usr/bin", *args]
            self.require(args, "The Omarchy setup step failed.", retry="ports" if "ufw" in function else "repair", interactive=True)

    def stop_processes(self, rows, retry="repair"):
        for row in rows:
            if process_identity(row["pid"], self.proc) == row["identity"]:
                try:
                    os.kill(row["pid"], signal.SIGTERM)
                except ProcessLookupError:
                    pass
        end = time.monotonic() + 6
        while time.monotonic() < end:
            if not any(process_identity(p["pid"], self.proc) == p["identity"] for p in rows):
                return
            time.sleep(0.15)
        raise Failure("Sunshine did not stop cleanly.", "Close Sunshine on this computer, then retry.", retry)

    def repair(self):
        if not self.system.have("sunshine"):
            raise Failure("Sunshine is not installed.", "Use Install to set up this computer.", "install")
        if self.status()["streaming"]:
            raise Failure("End the current stream before Repair.", "Quit Beam Desktop in Moonlight, then retry.")
        self.display.stop()
        apps_changed = self.display.install()
        display_changed = self.display.virtual.install()
        for unit, enabled in self.units():
            if enabled:
                self.require(["systemctl", "--user", "disable", "--now", unit], "Could not disable Sunshine's duplicate startup.")
        browser_changed = self.browser.install()
        self.stock_function("install_admin_webapp")
        if not self.firewall()["firewallReady"]:
            self.stock_function("open_ufw_ports", root=True)
        rows = self.processes()
        if len(rows) > 1 or (rows and (apps_changed or display_changed or browser_changed or not rows[0].get("browser", False))):
            self.stop_processes(rows)
            rows = []
        if not rows:
            self.cache.mkdir(parents=True, exist_ok=True, mode=0o700)
            with (self.cache / "launch.log").open("wb") as output:
                command = [str(self.browser.launcher)]
                if self.system.have("uwsm-app"):
                    command = ["uwsm-app", "--", *command]
                self.system.spawn(command, output=output)
        end = time.monotonic() + 12
        while time.monotonic() < end:
            if len(self.processes()) == 1:
                break
            time.sleep(0.3)
        if len(self.processes()) != 1:
            raise Failure("Sunshine could not start.", "Open Sunshine's log from its admin page or retry Repair.")
        if not self.browser.ready():
            raise Failure("Sunshine startup was not saved.", "Retry Repair after checking the terminal error.")
        if not self.firewall()["firewallReady"]:
            raise Failure("Streaming ports could not be verified.", "Retry Ports in the setup terminal.", "ports")

    def perform(self, action):
        if action == "install":
            self.progress(action, "Installing Sunshine and the iPad QR helper. Enter your password only in this terminal.")
            # Installing QR first makes a cancelled package transaction observable.
            self.require(["omarchy-pkg-add", "qrencode"], "The QR helper did not install.", "install", 1800, True)
            if not self.system.have("sunshine"):
                rc, _ = self.run(["omarchy-install-service-sunshine"], timeout=1800, interactive=True)
                if rc:
                    units = self.units()
                    known_rename = self.system.have("sunshine") and any(u[0] == UNITS[0] for u in units) and not any(u[0] == UNITS[1] for u in units)
                    if not known_rename:
                        raise Failure("Sunshine installation stopped.", f"The installer exited with code {rc}. Check its terminal message and retry.", "install")
                    self.progress(action, "Finishing setup after the packaged service-name mismatch.")
            self.repair()
            return result(True, action, "This computer's installation is complete.", "Create your Sunshine login, then pair Moonlight on the iPad.")
        if action == "repair":
            self.progress(action, "Checking startup and finishing the Omarchy setup.")
            self.repair()
            return result(True, action, "Sunshine startup and streaming ports are ready.", "The live checks will confirm capture when Sunshine reports it.")
        if action == "ports":
            self.progress(action, "Applying Omarchy's streaming port rules.")
            self.stock_function("open_ufw_ports", root=True)
            if not self.firewall()["firewallReady"]:
                raise Failure("Streaming ports could not be verified.", "Check the terminal and retry Ports.", "ports")
            return result(True, action, "Streaming port rules are ready.")
        if action == "undo":
            self.progress(action, "Removing Sunshine, its paired devices and Omarchy setup.")
            for unit, _ in self.units():
                self.require(["systemctl", "--user", "disable", "--now", unit], "Could not stop Sunshine's service.", "undo")
            self.stop_processes(self.processes(), retry="undo")
            self.display.stop()
            self.display.virtual.remove()
            self.require(["omarchy-remove-service-sunshine"], "Sunshine removal stopped.", "undo", 1800, True)
            self.browser.remove()
            # The stock remover leaves user credentials and pairings. Remove the
            # default app config only, after the user has confirmed this in QML.
            if self.sun.is_symlink():
                raise Failure("Sunshine uses a linked configuration folder.", "Remove that configuration yourself; Beam did not follow the link.", "")
            if self.sun.exists():
                shutil.rmtree(self.sun)
            if self.system.have("sunshine") or self.processes() or self.firewall()["ufwRules"]:
                raise Failure("Some Sunshine components remain.", "Check the terminal and retry Remove.", "undo")
            return result(True, action, "Sunshine and its saved pairing data were removed.", "Existing iPads must pair again after reinstalling.")
        raise Failure("This action is not available.", retry="")

    def execute(self, action):
        if not sys.stdin.isatty():
            return result(False, action, "This action needs the visible setup terminal.", "Open it from Beam so you can enter your password yourself.", action)
        if os.geteuid() == 0:
            return result(False, action, "Open Beam in your normal desktop session.", "Only package and firewall steps should run with administrator rights.", action)
        try:
            with self.lock():
                try:
                    self.progress(action, "Starting " + action + ".")
                    done = self.perform(action)
                except (Failure, DisplayError) as exc:
                    done = result(False, action, exc.message, exc.detail, exc.retry)
                except (OSError, ValueError) as exc:
                    done = result(False, action, "The action could not finish.", "Check the setup terminal and retry.", action)
                    print(type(exc).__name__ + ": " + str(exc), file=sys.stderr)
                previous = read_json(self.state / "action.json")
                done.update(id=previous.get("id", ""), state="success" if done["ok"] else "error", busy=False, phase="complete" if done["ok"] else "failed", updatedAt=time.time() * 1000)
                atomic_json(self.state / "action.json", done)
                return done
        except Failure as exc:
            return result(False, action, exc.message, exc.detail, exc.retry)

    def terminal(self, action):
        if action not in PRIVILEGED:
            return result(False, "terminal", "This setup action is unavailable.")
        try:
            with self.lock():
                if self.action_state().get("busy"):
                    return result(False, action, "The setup terminal is already open.", "Finish that action first.")
                if not self.system.have("omarchy-launch-terminal"):
                    return result(False, action, "Omarchy's terminal launcher is unavailable.", "Update Omarchy and try again.", action)
                # Pass an argv array. The presentation wrapper joins argv into a
                # shell command and also prints 'Done' after failed actions.
                pending = result(True, action, "Opening the setup terminal.", id=uuid.uuid4().hex, state="working", busy=True, terminal=True, phase="opening", updatedAt=time.time() * 1000)
                atomic_json(self.state / "action.json", pending)
                try:
                    self.system.spawn(["omarchy-launch-terminal", str(self.entry), "run-terminal", action])
                except OSError:
                    done = result(False, action, "The setup terminal could not open.", "Try again from Beam.", action, busy=False)
                    atomic_json(self.state / "action.json", done)
                    return done
            return pending
        except Failure as exc:
            return result(False, action, exc.message, exc.detail, exc.retry)

    def qr(self, text):
        if not text or len(text.encode()) > 2048:
            return result(False, "qr", "There is no valid QR content yet.")
        if not self.system.have("qrencode"):
            return result(False, "qr", "The QR helper is not installed.", "Use Install, then reopen this step.", "install")
        try:
            self.cache.mkdir(parents=True, exist_ok=True, mode=0o700)
            target = self.cache / ("qr-" + hashlib.sha256(text.encode()).hexdigest() + ".png")
            if not target.exists() or target.stat().st_size < 8:
                fd, temp = tempfile.mkstemp(prefix="qr-", suffix=".png", dir=self.cache)
                os.close(fd)
                try:
                    rc, _ = self.run(["qrencode", "-t", "PNG", "-o", temp, "-s", "6", "-m", "4", "-l", "M", "--foreground=000000", "--background=FFFFFF", "--", text])
                    if rc or Path(temp).read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                        return result(False, "qr", "The QR code could not be generated.", "Use the address or App Store link shown here.", "")
                    os.replace(temp, target)
                finally:
                    with contextlib.suppress(FileNotFoundError):
                        os.unlink(temp)
            # Keep only a small address-change history.
            for stale in sorted(self.cache.glob("qr-*.png"), key=lambda p: p.stat().st_mtime, reverse=True)[16:]:
                stale.unlink(missing_ok=True)
            return result(True, "qr", "QR code ready.", path=str(target))
        except OSError:
            return result(False, "qr", "The QR code could not be saved.", "Use the address or App Store link shown here.")

    def open_admin(self, pin=False):
        status = self.status()
        if not status["adminUp"]:
            return result(False, "pin" if pin else "admin", "Sunshine's setup page is not ready.", "Use Repair to start Sunshine, then try again.", "repair")
        url = status["adminUrl"] + ("/pin" if pin else "")
        # Keep Admin and PIN in the same private browser context. Extensions
        # in the regular profile can suppress Sunshine's HTTP login prompt.
        command = ["omarchy-launch-browser", "--private", url] if self.system.have("omarchy-launch-browser") else ["xdg-open", url]
        try:
            self.system.spawn(command)
            return result(True, "pin" if pin else "admin", "Sunshine's page is opening in your browser.", "Sign in with your Sunshine login. Keep this private window open for pairing; its local certificate warning is expected.")
        except OSError:
            return result(False, "pin" if pin else "admin", "The browser could not open.", "Open " + url + " in your browser.")

    def moonlight(self):
        try:
            self.system.spawn(["xdg-open", APP_STORE])
            return result(True, "moonlight", "Moonlight's App Store page is opening.", "On the iPad, scan the QR code to install it.")
        except OSError:
            return result(False, "moonlight", "The browser could not open.", "Scan the QR code with your iPad camera.")

    def copy_address(self):
        address = self.status()["address"]
        if not address:
            return result(False, "copy-address", "This computer has no usable address.")
        if not self.system.have("wl-copy") or not self.system.copy(address):
            return result(False, "copy-address", "The address could not be copied.", "Use the address shown in Beam.")
        return result(True, "copy-address", "Address copied.", "Paste it into Moonlight's Add PC field.")

    def greet(self):
        marker = self.state / "greeted"
        with self.lock():
            if marker.exists():
                return result(True, "greet", "Welcome already shown.")
            if not self.status()["ready"]:
                rc, _ = self.run(["omarchy-notification-send", "--app-name", "Beam", "Beam is ready to set up", "Click the Beam dot to put this desktop on your iPad.", "--exec", "omarchy-shell", "nixfred.beam", "open"])
                if rc:
                    return result(False, "greet", "The welcome notification could not be shown.")
            marker.touch(mode=0o600)
            return result(True, "greet", "Welcome shown.")


def fallback_status():
    return dict(installed=False, running=False, processes=0, version="", unit="", unitEnabled=False,
                autostart=False, browserReady=False, ufwRules=0, ufwPresent=False, firewallReady=False, firewallKnown=False,
                firewallState="unknown", adminUp=False, adminConfigured=False, adminKnown=False,
                adminUrl="https://localhost:47990", displayFound=False, encoder="", encoderKind="unknown",
                recommendedRes="Full · 60 fps", recommendedBitrate=20, pairedClients=0,
                resolutionReady=False, resolutionActive=False, resolutionDetail="Use Repair to enable automatic iPad sizing.",
                streaming=False, streamCount=0, locked=False, address="", addressKind="none", lanAddress="",
                nextStep=2, ready=False, setupReady=False, qrAvailable=False, appStoreUrl=APP_STORE,
                inputReady=False, actionBusy=False, lastAction={}, checks=[],
                issues=[dict(code="probe", message="Beam could not check this computer.", action="", detail="Reopen Beam to retry.")])


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    action = args.pop(0) if args else "status"
    beam = Beam()
    try:
        if action in ("status", "doctor"):
            try:
                data = beam.status()
            except Exception:
                data = fallback_status()
            if action == "doctor":
                print("Beam checks")
                for check in data["checks"]:
                    print(("OK: " if check["ok"] else "CHECK: ") + check["label"])
                for issue in data["issues"]:
                    print(issue["message"] + " " + issue.get("detail", ""))
                return 0
        elif action == "terminal":
            data = beam.terminal(args[0] if args else "")
        elif action == "run-terminal":
            data = beam.execute(args[0] if args else "")
            print("\n" + data["message"] + "\n" + data["detail"], file=sys.stderr)
            if sys.stdin.isatty():
                try:
                    input("\nPress Enter to return to Beam. ")
                except EOFError:
                    pass
        elif action in PRIVILEGED:
            data = beam.execute(action)
        elif action == "qr":
            data = beam.qr(args[0] if args else "")
        elif action in ("admin", "pin"):
            data = beam.open_admin(action == "pin")
        elif action == "moonlight":
            data = beam.moonlight()
        elif action == "copy-address":
            data = beam.copy_address()
        elif action == "prepare-display":
            beam.display.virtual.prepare()
            data = result(True, action, "The iPad capture display is ready.")
        elif action == "set-resolution":
            fixed = beam.display.set_resolution(args[0] if args else "")
            message = f"Desktop pinned to {fixed[0]}×{fixed[1]} at {fixed[2]} FPS." if fixed else "Desktop sizing follows Moonlight again."
            detail = f"Set Moonlight Custom to {fixed[0]}×{fixed[1]}, then quit and relaunch the desktop." if fixed else "Choose Full in Moonlight, then quit and relaunch the desktop."
            data = result(True, action, message, detail)
        elif action == "stream-start":
            session = beam.display.start()
            data = result(True, action, "The desktop now uses Beam's selected stream size.",
                          requested=session["requested"], applied=session["applied"])
        elif action in ("stream-stop", "restore-display"):
            restored = beam.display.stop()
            message = "The saved display layout has been restored." if restored else "Your manual display change was kept." if restored is False else "No display resize is active."
            data = result(True, action, message, "Open Beam Desktop again to start a new stream.")
        elif action == "stream-session":
            beam.display.supervise()
            data = result(True, action, "The iPad display session has ended.")
        elif action == "greet":
            data = beam.greet()
        elif action == "action-result":
            data = beam.action_state()
        elif action == "address":
            print(beam.addresses()["address"])
            return 0
        elif action == "hold":
            data = result(False, "hold", "Beam uses a session-owned idle inhibitor.", "The plugin manages it automatically; your stay-awake preference is preserved.")
        else:
            data = result(False, action, "Unknown internal action.")
    except DisplayError as exc:
        if action in ("stream-start", "stream-stop", "stream-session", "restore-display"):
            beam.display.record_error(exc)
        data = result(False, action, exc.message, exc.detail, "restore-display" if action in ("stream-stop", "restore-display") else exc.retry)
    except Exception:
        data = result(False, action, "Beam could not finish this action.", "Reopen the panel and try again.", action if action in PRIVILEGED else "")
    print(json.dumps(data, ensure_ascii=False))
    return 0 if action == "status" or data.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
