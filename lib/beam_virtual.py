"""A persistent, named capture output independent of physical panel modes."""
import json
import uuid

from beam_display import DisplayError, load, save

OUTPUT = "BEAM-IPAD"
IDLE = "beam-idle"


def readable_scale(width, height):
    # Native iPad pixels stay sharp while controls use a tablet-sized workspace.
    for scale in (2, 1.5, 1.25, 1):
        w, h = width / scale, height / scale
        if w >= 960 and h >= 640 and w.is_integer() and h.is_integer():
            return scale
    return 1


class VirtualDisplay:
    def __init__(self, fit):
        self.fit, self.beam = fit, fit.beam
        self.preferences = self.beam.state / "display-virtual.json"

    def enabled(self):
        return bool(load(self.preferences))

    def command(self, code):
        rc, output = self.beam.run(["hyprctl", "eval", code])
        if rc or output.strip() != "ok":
            raise DisplayError("Hyprland could not prepare the iPad desktop.", "Use Restore display, then Repair in Beam.")

    def monitors(self):
        return self.fit.monitors(all_outputs=True)

    def source(self):
        monitors = [m for m in self.monitors() if m["name"] != OUTPUT and not m.get("disabled", False)
                    and m.get("mirrorOf", "none") == "none"]
        selected = self.beam.config_values().get("output_name", "")
        if selected and selected != "0":
            matches = [m for m in monitors if m["name"] == selected]
            if len(matches) == 1:
                return matches[0]
        elif len(monitors) == 1:
            return monitors[0]
        raise DisplayError("Choose the desktop to send to the iPad.", "Set Sunshine's Output Name to the physical monitor's connector name, then Repair.")

    def workspaces(self):
        rc, output = self.beam.run(["hyprctl", "-j", "workspaces"])
        try:
            rows = json.loads(output)
        except ValueError:
            rows = None
        if rc or not isinstance(rows, list):
            raise DisplayError("Beam cannot read the desktop workspaces.")
        return rows

    @staticmethod
    def selector(workspace):
        if workspace["id"] > 0:
            return str(workspace["id"])
        name = workspace["name"]
        return json.dumps(name if name.startswith("special:") else "name:" + name)

    def move(self, workspace, monitor):
        self.command("hl.dispatch(hl.dsp.workspace.move({ workspace = %s, monitor = %s }))" %
                     (self.selector(workspace), json.dumps(monitor)))

    def focus(self, monitor, workspace=None):
        self.command("hl.dispatch(hl.dsp.focus({ monitor = %s }))" % json.dumps(monitor))
        if workspace and any(w["id"] == workspace["id"] for w in self.workspaces()):
            self.command("hl.dispatch(hl.dsp.focus({ workspace = %s }))" % self.selector(workspace))

    def idle(self, source, focus=True):
        monitors = [m for m in self.monitors() if m.get("mirrorOf", "none") == "none"] + [source]
        right = max(int(m["x"] + m["width"] / m["scale"]) for m in monitors
                    if m["name"] != OUTPUT and not m.get("disabled", False))
        self.fit.apply(OUTPUT, dict(width=2048, height=1536, mode="2048x1536@60", refreshRate=60,
                                    scale=2, x=right + 1024, y=0, transform=0))
        self.focus(OUTPUT)
        self.command('hl.dispatch(hl.dsp.focus({ workspace = "name:' + IDLE + '", on_current_monitor = true }))')
        if focus:
            self.focus(source["name"], source.get("activeWorkspace"))

    def prepare(self):
        """Called before Sunshine starts, so it enumerates the named output."""
        with self.fit.lock():
            if load(self.fit.state):
                self.fit.restore(load(self.fit.state))
            source = self.source()
            existing = [m for m in self.monitors() if m["name"] == OUTPUT]
            created = not existing
            if created:
                # Give the new output a position before hotplug. Otherwise an
                # automatic monitor layout can move the physical desktop.
                right = max(int(m["x"] + m["width"] / m["scale"]) for m in self.monitors() if not m.get("disabled", False))
                self.command('hl.monitor({ output = "%s", mode = "2048x1536@60", position = "%sx0", scale = 2 })' %
                             (OUTPUT, right + 1024))
                rc, output = self.beam.run(["hyprctl", "output", "create", "headless", OUTPUT])
                if rc or output.strip() != "ok":
                    raise DisplayError("The iPad capture display could not be created.")
            try:
                self.idle(source)
            except DisplayError:
                if created:
                    self.beam.run(["hyprctl", "output", "remove", OUTPUT])
                raise

    def install(self):
        self.source()  # Fail before changing setup if the source is ambiguous.
        expected = dict(entry=str(self.beam.entry), output=OUTPUT)
        previous = load(self.preferences)
        if previous == expected:
            return not any(m["name"] == OUTPUT for m in self.monitors())
        if not previous and any(m["name"] == OUTPUT for m in self.monitors()):
            raise DisplayError("Another display already uses Beam's capture name.", "Rename that display before running Repair.")
        save(self.preferences, expected)
        # Migrate the old 16:9 workaround to native client dimensions.
        self.fit.preferences.unlink(missing_ok=True)
        return True

    def start(self, requested, owner):
        source = self.source()
        monitor = next((m for m in self.monitors() if m["name"] == OUTPUT), None)
        if not monitor:
            raise DisplayError("The iPad capture display is missing.", "Quit the stream and use Repair before reconnecting.")
        fixed = self.fit.fixed_size()
        width, height, fps = fixed or requested
        applied = dict(width=width, height=height, pictureWidth=width, pictureHeight=height,
                       mode=f"{width}x{height}@{min(fps, 60)}", refreshRate=min(fps, 60),
                       scale=readable_scale(width, height), x=source["x"], y=source["y"], transform=0, exact=True)
        workspaces = [w for w in self.workspaces() if w["monitor"] == source["name"]]
        session = dict(token=uuid.uuid4().hex, kind="virtual", monitor=OUTPUT,
                       original=self.fit.original(monitor), applied=applied, requested=list(requested),
                       target=[width, height, fps], fixed=bool(fixed), owner=owner,
                       source=source["name"], sourceOriginal=self.fit.original(source),
                       sourceWorkspace=source.get("activeWorkspace"), workspaces=workspaces)
        save(self.fit.state, session)
        try:
            # Change size away from the local screen first. Moving into its
            # position before enabling the mirror briefly overlaps two outputs.
            staging = dict(applied, x=monitor["x"], y=monitor["y"])
            self.fit.apply(OUTPUT, staging)
            for workspace in workspaces:
                self.move(workspace, OUTPUT)
            self.fit.apply(source["name"], dict(session["sourceOriginal"], mirror=OUTPUT,
                                               x=staging["x"], y=staging["y"]))
            self.fit.apply(OUTPUT, applied)
            self.focus(OUTPUT, session["sourceWorkspace"])
        except DisplayError:
            self.restore(session)
            raise
        self.fit.error.unlink(missing_ok=True)
        return session

    def restore(self, session):
        monitors = self.monitors()
        source = next((m for m in monitors if m["name"] == session["source"]), None)
        virtual = next((m for m in monitors if m["name"] == OUTPUT), None)
        if not source:
            raise DisplayError("The original display is disconnected.", "Reconnect it and use Restore display in Beam.")
        # Only undo Beam's mirror. A newer manual layout wins.
        mirrored = virtual and str(source.get("mirrorOf")) == str(virtual["id"])
        try:
            active = virtual.get("activeWorkspace") if virtual else None
            if virtual:
                parked_source = dict(source, **session["sourceOriginal"]) if mirrored else source
                self.idle(parked_source, focus=False)
            if mirrored:
                self.fit.apply(source["name"], dict(session["sourceOriginal"], mirror=""))
            for workspace in self.workspaces():
                if workspace["monitor"] == OUTPUT and workspace["name"] != IDLE:
                    self.move(workspace, source["name"])
            self.focus(source["name"], active or session.get("sourceWorkspace"))
        except DisplayError as exc:
            session["error"] = exc.message + " Use Restore display."
            save(self.fit.state, session)
            raise
        self.fit.state.unlink(missing_ok=True)
        return True

    def remove(self):
        if self.enabled():
            self.fit.stop()
            if any(m["name"] == OUTPUT for m in self.monitors()):
                self.beam.run(["hyprctl", "output", "remove", OUTPUT])
            self.preferences.unlink(missing_ok=True)
