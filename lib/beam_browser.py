#!/usr/bin/env python3
"""Sunshine-only URL routing, also installed as two standalone launchers."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit

MARKER = "-- beam-sunshine-browser"
STOCK_AUTOSTART = 'o.launch_on_start("sunshine")'


def admin_port(config=None):
    config = Path(config) if config is not None else Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    try:
        with (config / "sunshine/sunshine.conf").open() as stream:
            for line in stream:
                key, _, value = line.partition("=")
                if key.strip() == "port":
                    port = int(value.strip()) + 1
                    return port if 1024 <= port <= 65535 else 47990
    except (OSError, ValueError):
        pass
    return 47990


def browser_command(args, port, have_browser):
    if len(args) == 1 and have_browser:
        try:
            url = urlsplit(args[0])
            if (url.scheme == "https" and url.hostname in ("localhost", "127.0.0.1", "::1")
                    and url.port == port and url.username is None and url.password is None):
                # Use the same origin as Beam's buttons, sharing HTTP login state.
                target = urlunsplit(("https", f"localhost:{port}", url.path, url.query, url.fragment))
                return ["omarchy-launch-browser", "--private", target]
        except ValueError:
            pass
    return ["/usr/bin/xdg-open", *args]


def launch():
    if Path(sys.argv[0]).name == "xdg-open":
        # The override belongs to Sunshine, never to the user's browser session.
        if "BEAM_SUNSHINE_ORIGINAL_PATH" in os.environ:
            os.environ["PATH"] = os.environ.pop("BEAM_SUNSHINE_ORIGINAL_PATH")
        os.environ.pop("BEAM_SUNSHINE_BROWSER", None)
        command = browser_command(sys.argv[1:], admin_port(), bool(shutil.which("omarchy-launch-browser")))
        os.execvp(command[0], command)
    else:
        binary = shutil.which("sunshine")
        if not binary:
            raise SystemExit("Sunshine is not installed.")
        virtual = Path(__file__).resolve().parent.parent / "display-virtual.json"
        overrides = []
        if virtual.exists():
            settings = json.loads(virtual.read_text())
            prepared = subprocess.run([settings["entry"], "prepare-display"], check=False)
            if prepared.returncode:
                raise SystemExit("Beam could not prepare the iPad capture display. Use Repair.")
            overrides = ["output_name=" + settings["output"], "capture=wlr"]
        original = os.environ.get("PATH", os.defpath)
        os.environ["BEAM_SUNSHINE_ORIGINAL_PATH"] = original
        os.environ["BEAM_SUNSHINE_BROWSER"] = "1"
        os.environ["PATH"] = str(Path(__file__).resolve().parent) + os.pathsep + original
        # File capabilities can make Sunshine's /proc/environ unreadable. Exec
        # preserves this PID and start time, so record ownership before exec.
        stat = Path("/proc/self/stat").read_text()
        identity = stat[stat.rfind(")") + 2:].split()[19]
        record = dict(pid=os.getpid(), identity=identity, version=1)
        BrowserBridge.write(Path(__file__).resolve().parent / "process.json",
                            json.dumps(record).encode(), 0o600)
        os.execv(binary, [binary, *sys.argv[1:], *overrides])


class BrowserBridge:
    def __init__(self, state, autostart):
        self.directory = Path(state) / "browser"
        self.autostart = Path(autostart)
        self.launcher = self.directory / "launch-sunshine"

    def line(self):
        return "o.launch_on_start(" + json.dumps(shlex.quote(str(self.launcher))) + ") " + MARKER

    def owns_process(self, pid, identity):
        try:
            record = json.loads((self.directory / "process.json").read_text())
            return record == dict(pid=pid, identity=identity, version=1)
        except (OSError, ValueError):
            return False

    def ready(self):
        try:
            source = Path(__file__).read_bytes()
            lines = self.autostart.read_text().splitlines()
            return (lines.count(self.line()) == 1 and not any(line.strip() == STOCK_AUTOSTART for line in lines)
                    and all(p.read_bytes() == source and os.access(p, os.X_OK)
                            for p in (self.launcher, self.directory / "xdg-open")))
        except OSError:
            return False

    @staticmethod
    def write(path, data, mode):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(prefix=".beam-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                os.fchmod(stream.fileno(), mode)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def install(self):
        if self.ready():
            return False
        original = self.autostart.read_bytes() if self.autostart.exists() else b""
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        backup = self.directory / "autostart.before.lua"
        if not backup.exists():
            self.write(backup, original, 0o600)
        source = Path(__file__).read_bytes()
        for path in (self.launcher, self.directory / "xdg-open"):
            self.write(path, source, 0o700)
        lines = [line for line in original.decode().splitlines()
                 if line.strip() != STOCK_AUTOSTART and not line.rstrip().endswith(MARKER)]
        lines.append(self.line())
        mode = self.autostart.stat().st_mode & 0o777 if self.autostart.exists() else 0o600
        self.write(self.autostart, ("\n".join(lines) + "\n").encode(), mode)
        return True

    def remove(self):
        if self.autostart.exists():
            original = self.autostart.read_text()
            lines = [line for line in original.splitlines() if not line.rstrip().endswith(MARKER)]
            self.write(self.autostart, ("\n".join(lines) + "\n").encode(), self.autostart.stat().st_mode & 0o777)


if __name__ == "__main__":
    launch()
