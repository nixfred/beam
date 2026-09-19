"""Client-sized, reversible Hyprland display modes for Beam's Sunshine app."""
from __future__ import annotations

import contextlib
import fcntl
import json
import math
import os
from pathlib import Path
import re
import shlex
import signal
import tempfile
import time
import uuid

APP_NAME = "Beam Desktop"
MODE = re.compile(r"^(\d+)x(\d+)@([\d.]+)(?:Hz)?$")


class DisplayError(Exception):
    def __init__(self, message, detail="Use Repair in Beam, then reconnect."):
        self.message, self.detail, self.retry = message, detail, "repair"


def load(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {} if default is None else default
    except (OSError, ValueError):
        raise DisplayError("Beam could not read the saved display setup.", "The existing file was left unchanged.")


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".beam-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def requested_size(environ):
    try:
        values = tuple(int(environ["SUNSHINE_CLIENT_" + key]) for key in ("WIDTH", "HEIGHT", "FPS"))
    except (KeyError, ValueError, TypeError):
        raise DisplayError("Moonlight did not send a valid picture size.", "Select Full in Moonlight, then start Beam Desktop again.")
    width, height, fps = values
    if not (320 <= width <= 8192 and 320 <= height <= 8192 and width * height <= 33554432 and 1 <= fps <= 240):
        raise DisplayError("Moonlight requested an unsupported picture size.", "Choose Full and 60 FPS in Moonlight.")
    return values


def choose_mode(monitor, requested):
    """Use advertised modes only; never send an untested modeline to a panel."""
    width, height, fps = requested
    rotated = int(monitor.get("transform", 0)) % 2 == 1
    choices = []
    for text in monitor.get("availableModes", []):
        match = MODE.fullmatch(text)
        if not match:
            continue
        native_w, native_h, hz = int(match[1]), int(match[2]), float(match[3])
        w, h = (native_h, native_w) if rotated else (native_w, native_h)
        if not (320 <= w <= width and 320 <= h <= height and math.isfinite(hz) and 20 <= hz <= 240):
            continue
        # Exact ratio first, then useful detail, then the nearest refresh rate.
        aspect_error = abs(math.log((w / h) / (width / height)))
        choices.append(((round(aspect_error, 3), -(w * h), abs(hz - min(fps, 60))),
                        dict(width=native_w, height=native_h, pictureWidth=w, pictureHeight=h,
                             mode=f"{native_w}x{native_h}@{hz:g}", refreshRate=hz)))
    if not choices:
        raise DisplayError("This display has no supported mode that fits the iPad request.", "Choose a larger Moonlight picture size or another Sunshine display. Beam kept the original desktop.")
    chosen = min(choices, key=lambda item: item[0])[1]
    chosen["exact"] = chosen["pictureWidth"] == width and chosen["pictureHeight"] == height
    return chosen


class DisplayFit:
    def __init__(self, beam):
        from beam_virtual import VirtualDisplay
        self.beam = beam
        self.state = beam.state / "display-session.json"
        self.error = beam.state / "display-error.json"
        self.preferences = beam.state / "display-preferences.json"
        self.virtual = VirtualDisplay(self)

    def fixed_size(self):
        value = load(self.preferences)
        if not value:
            return None
        if not isinstance(value, dict):
            raise DisplayError("The saved fixed resolution is invalid.")
        return requested_size({"SUNSHINE_CLIENT_" + key.upper(): value.get(key)
                               for key in ("width", "height", "fps")})

    @staticmethod
    def validate_scale(size, value):
        try:
            scale = float(value)
        except (ValueError, TypeError):
            raise DisplayError("Use a desktop scale between 1 and 2.")
        if not math.isfinite(scale) or not 1 <= scale <= 2:
            raise DisplayError("Use a desktop scale between 1 and 2.")
        width, height = size[0] / scale, size[1] / scale
        if (not math.isclose(width, round(width), abs_tol=0.00001)
                or not math.isclose(height, round(height), abs_tol=0.00001)
                or (scale > 1 and (width < 960 or height < 640))):
            raise DisplayError("That scale does not fit this custom resolution cleanly.", "Use scale 1 or a scale that produces whole desktop pixels.")
        return scale

    def fixed_scale(self):
        size = self.fixed_size()
        return self.validate_scale(size, load(self.preferences).get("scale", 1)) if size else 1

    def set_resolution(self, value, scale=1):
        with self.lock():
            if value == "auto":
                self.preferences.unlink(missing_ok=True)
                self.error.unlink(missing_ok=True)
                return None
            match = re.fullmatch(r"(\d+)x(\d+)", value)
            if not match:
                raise DisplayError("Use WIDTHxHEIGHT or auto for the desktop resolution.")
            target = requested_size({"SUNSHINE_CLIENT_WIDTH": match[1],
                                     "SUNSHINE_CLIENT_HEIGHT": match[2], "SUNSHINE_CLIENT_FPS": 60})
            scale = self.validate_scale(target, scale)
            if not self.virtual.enabled() and not choose_mode(self.monitor(), target)["exact"]:
                raise DisplayError("This display does not support that fixed resolution.", "Choose an advertised display mode. The previous setting was kept.")
            save(self.preferences, dict(zip(("width", "height", "fps"), target), scale=scale))
            self.error.unlink(missing_ok=True)
            return target

    @contextlib.contextmanager
    def lock(self):
        self.state.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.state.with_suffix(".lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def app_path(self):
        path = Path(self.beam.config_values().get("file_apps", "apps.json"))
        return path if path.is_absolute() else self.beam.sun / path

    def app(self, name=APP_NAME):
        command = shlex.quote(str(self.beam.entry)).replace("$", "$$")
        return {"name": name, "beam-managed": 1, "image-path": "desktop.png",
                "cmd": command + " stream-session", "auto-detach": False,
                "wait-all": False, "exit-timeout": 5,
                "prep-cmd": [{"do": command + " stream-start", "undo": command + " stream-stop", "elevated": False}]}

    def configured_apps(self, apps):
        matches = [a for a in apps if isinstance(a, dict) and a.get("name") == APP_NAME]
        if len(matches) > 1 or (matches and matches[0].get("beam-managed") != 1):
            raise DisplayError("An existing app already uses the name Beam Desktop.", "Rename that app in Sunshine, then retry Repair.")
        desktops = [a for a in apps if isinstance(a, dict) and a.get("name") == "Desktop"]
        output = []
        for app in apps:
            if isinstance(app, dict) and app.get("name") == APP_NAME:
                output.append(self.app())
            elif (len(desktops) == 1 and app is desktops[0]
                  and (app.get("beam-managed") == 1 or app in (
                      {"name": "Desktop"}, {"name": "Desktop", "image-path": "desktop.png"}))):
                # The stock tile is the obvious first choice in Moonlight.
                # Give it the same lifecycle without changing customized apps.
                output.append(self.app("Desktop"))
            else:
                output.append(app)
        if not matches:
            output.append(self.app())
        return output

    def install(self):
        path = self.app_path()
        if path.is_symlink():
            raise DisplayError("Sunshine's app list is a symbolic link.", "Use a regular apps.json file before enabling automatic sizing.")
        default = {"env": {}, "apps": [{"name": "Desktop", "image-path": "desktop.png"}]}
        data = load(path, default)
        if not isinstance(data, dict) or not isinstance(data.get("apps"), list):
            raise DisplayError("Sunshine's app list is invalid.", "The existing app list was left unchanged.")
        expected = self.configured_apps(data["apps"])
        if data["apps"] == expected:
            return False
        if path.exists():
            backup = self.beam.state / ("apps-before-sizing-" + time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6] + ".json")
            save(backup, data)
        data["apps"] = expected
        save(path, data)
        return True

    def status(self):
        try:
            data = load(self.app_path())
            apps = data.get("apps") if isinstance(data, dict) else None
            configured = isinstance(apps, list) and apps == self.configured_apps(apps)
            session = load(self.state)
            if not isinstance(session, dict):
                raise DisplayError("The saved display session is invalid.")
            current = session.get("applied", {})
            requested = session.get("requested", [])
            active = bool(session.get("token"))
            error = load(self.error).get("message", "")
            fixed = self.fixed_size()
            native = self.virtual.enabled()
            if native:
                from beam_virtual import OUTPUT
                configured = configured and any(m["name"] == OUTPUT for m in self.virtual.monitors())
            setting = f"Custom {fixed[0]}×{fixed[1]}" if fixed else "Full"
            text = "Full · 60 fps"
            detail = "Choose Full in Moonlight. Open Beam Desktop."
            if active and len(requested) == 3:
                text = f"iPad request {requested[0]}×{requested[1]}"
                detail = f"Desktop {current.get('pictureWidth', current['width'])}×{current.get('pictureHeight', current['height'])} · " + ("exact fit" if current.get("exact") else "closest supported fit")
                if session.get("kind") == "virtual":
                    detail += f" · {current['scale'] * 100:g}% text"
            if fixed:
                text = f"Fixed {fixed[0]}×{fixed[1]} · {self.fixed_scale() * 100:.3g}% scale"
                detail = f"Set Moonlight to {setting}. Open Beam Desktop."
                if active and len(requested) == 3:
                    detail = f"Desktop {current.get('pictureWidth', current['width'])}×{current.get('pictureHeight', current['height'])}. "
                    detail += ("Moonlight matches." if requested[:2] == list(fixed[:2]) else
                               f"Moonlight requests {requested[0]}×{requested[1]}; set {setting}.")
            return dict(resolutionReady=configured, resolutionActive=active, recommendedRes=text,
                        resolutionDetail=error or session.get("error", detail), resolutionError=error,
                        resolutionPinned=bool(fixed), moonlightSetting=setting, nativeResolution=native)
        except (DisplayError, KeyError, TypeError):
            return dict(resolutionReady=False, resolutionActive=False,
                        recommendedRes="Full · 60 fps", resolutionDetail="Use Repair to enable automatic iPad sizing.", resolutionError="",
                        resolutionPinned=False, moonlightSetting="Full")

    def monitors(self, all_outputs=False):
        rc, output = self.beam.run(["hyprctl", "-j", "monitors", *(["all"] if all_outputs else [])])
        try:
            monitors = json.loads(output)
        except ValueError:
            monitors = None
        if rc or not isinstance(monitors, list) or not monitors:
            raise DisplayError("Beam cannot read this desktop's display modes.", "Start Beam from the active Omarchy session.")
        return monitors

    def monitor(self):
        monitors = self.monitors()
        selected = self.beam.config_values().get("output_name", "")
        if selected:
            matches = [m for m in monitors if m.get("name") == selected]
            if len(matches) == 1:
                return matches[0]
            # A numeric Sunshine display ID is not a Hyprland monitor ID.
            if len(monitors) != 1 or selected not in ("0",):
                raise DisplayError("Choose Sunshine's display by connector name.", "Set Output Name in Sunshine to the intended monitor name, then reconnect.")
        if len(monitors) == 1:
            return monitors[0]
        raise DisplayError("Choose which display Beam should resize.", "Set Output Name in Sunshine to the monitor's connector name. Beam will not guess between displays.")

    @staticmethod
    def original(monitor):
        w, h = int(monitor["width"]), int(monitor["height"])
        # Hyprland reports m_pixelSize here, before the output transform.
        return dict(width=monitor["width"], height=monitor["height"],
                    mode=f"{w}x{h}@{float(monitor['refreshRate']):.5f}", refreshRate=monitor["refreshRate"],
                    scale=monitor["scale"], x=monitor["x"], y=monitor["y"], transform=monitor.get("transform", 0))

    def apply(self, name, mode):
        if not re.fullmatch(r"[A-Za-z0-9_.:-]+", name):
            raise DisplayError("The display connector name is unsupported.")
        extra = ", mirror = %s, transform = %s" % (json.dumps(mode["mirror"]), int(mode.get("transform", 0))) if "mirror" in mode else ""
        code = "hl.monitor({ output = %s, mode = %s, position = %s, scale = %s%s })" % (
            json.dumps(name), json.dumps(mode["mode"]),
            json.dumps(f"{int(mode['x'])}x{int(mode['y'])}"), float(mode["scale"]), extra)
        rc, output = self.beam.run(["hyprctl", "eval", code])
        if rc or output.strip() != "ok":
            raise DisplayError("Hyprland could not apply the requested display mode.")
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            monitors = self.monitors(all_outputs="mirror" in mode)
            for monitor in monitors:
                if monitor.get("name") != name or not self.matches(monitor, mode):
                    continue
                if "mirror" in mode:
                    target = next((str(m["id"]) for m in monitors if m["name"] == mode["mirror"]), "none")
                    if str(monitor.get("mirrorOf", "none")) != target:
                        continue
                return
            time.sleep(0.1)
        raise DisplayError("The display did not confirm its new mode.")

    @staticmethod
    def matches(current, expected):
        return ((current.get("width"), current.get("height"), current.get("x"), current.get("y"), current.get("transform", 0)) == (
            expected["width"], expected["height"], expected["x"], expected["y"], expected.get("transform", 0))
            and math.isclose(float(current.get("scale", 0)), expected["scale"], rel_tol=0, abs_tol=0.00001)
            and abs(float(current.get("refreshRate", 0)) - expected["refreshRate"]) < 0.1)

    def restore(self, session, force=False):
        if not session:
            return
        if session.get("kind") == "virtual":
            return self.virtual.restore(session)
        matches = [m for m in self.monitors() if m.get("name") == session["monitor"]]
        if not matches:
            raise DisplayError("The original display is disconnected.", "Reconnect it and use Restore display in Beam.")
        # Do not overwrite a deliberate display change made during the stream.
        restored = force or self.matches(matches[0], session["applied"])
        if restored:
            try:
                self.apply(session["monitor"], session["original"])
            except DisplayError as exc:
                session["error"] = exc.message + " Use Restore display."
                save(self.state, session)
                raise
        self.state.unlink(missing_ok=True)
        return restored

    def start(self, environ=None):
        requested = requested_size(os.environ if environ is None else environ)
        with self.lock():
            previous = load(self.state)
            if previous:
                self.restore(previous)
            processes = self.beam.processes()
            if len(processes) != 1:
                raise DisplayError("Automatic sizing requires one running Sunshine.")
            if self.virtual.enabled():
                return self.virtual.start(requested, processes[0])
            monitor = self.monitor()
            original = self.original(monitor)
            fixed = self.fixed_size()
            target = fixed or requested
            chosen = choose_mode(monitor, target)
            if fixed and not chosen["exact"]:
                raise DisplayError("The fixed desktop resolution is no longer supported.", "Choose another supported fixed mode or set the resolution back to auto.")
            applied = dict(original, **chosen)
            if fixed:
                applied["scale"] = self.fixed_scale()
            if applied["width"] / applied["scale"] < 960 or applied["height"] / applied["scale"] < 640:
                applied["scale"] = 1
            session = dict(token=uuid.uuid4().hex, monitor=monitor["name"], original=original,
                           applied=applied, requested=list(requested), target=list(target), fixed=bool(fixed), owner=processes[0])
            save(self.state, session)  # Recovery is durable before the first display change.
            try:
                self.apply(monitor["name"], applied)
            except DisplayError:
                self.restore(session, force=True)
                raise
            self.error.unlink(missing_ok=True)
            return session

    def stop(self, token=None):
        with self.lock():
            session = load(self.state)
            if token is None or session.get("token") == token:
                restored = self.restore(session)
                self.error.unlink(missing_ok=True)
                return restored

    def record_error(self, error):
        save(self.error, {"message": error.message, "detail": error.detail})

    def supervise(self):
        """This foreground Sunshine app ends after the last client disconnects."""
        session = load(self.state)
        if not session:
            raise DisplayError("The iPad display session was not prepared.")
        stopping = False
        def stop_signal(*_):
            nonlocal stopping
            stopping = True
        old_handlers = {sig: signal.signal(sig, stop_signal) for sig in (signal.SIGTERM, signal.SIGINT)}
        connected = False
        last_live = time.monotonic()
        values = self.beam.config_values()
        log = Path(values.get("log_path", "sunshine.log"))
        if not log.is_absolute():
            log = self.beam.sun / log
        try:
            while not stopping:
                rows = self.beam.processes()
                if not any(p["pid"] == session["owner"]["pid"] and p["identity"] == session["owner"]["identity"] for p in rows):
                    break
                if load(self.state).get("token") != session["token"]:
                    break
                # A theme reload, hotplug, or manual monitor change must not
                # silently turn this session back into an ultrawide capture.
                if not any(m.get("name") == session["monitor"] and self.matches(m, session["applied"]) for m in self.monitors()):
                    break
                if session.get("kind") == "virtual":
                    monitors = self.virtual.monitors()
                    virtual = next((m for m in monitors if m["name"] == session["monitor"]), {})
                    if not any(m["name"] == session["source"] and str(m.get("mirrorOf")) == str(virtual.get("id")) for m in monitors):
                        break
                if self.beam.log_facts(rows, log)["streaming"]:
                    connected = True
                    last_live = time.monotonic()
                elif time.monotonic() - last_live > (3 if connected else 30):
                    break
                time.sleep(0.5)
        finally:
            for sig, handler in old_handlers.items():
                signal.signal(sig, handler)
            self.stop(session["token"])
