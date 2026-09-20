"""Adversarial Beam probes. Isolated TemporaryDirectory homes and fake System only."""
from __future__ import annotations

import ast
import copy
import datetime as dt
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

spec = importlib.util.spec_from_file_location("beam", Path(__file__).resolve().parents[1] / "lib/beam.py")
beam = importlib.util.module_from_spec(spec)
spec.loader.exec_module(beam)

from beam_display import DisplayError, load, save
from beam_ipads import PROFILES, profile, profiles
from beam_virtual import OUTPUT, readable_scale
from test_display import DisplaySystem


class RecordingSystem:
    def __init__(self):
        self.commands = []
        self.have_names = {"ufw"}
        self.returncodes = {}

    def have(self, name):
        return name in self.have_names

    def run(self, args, **kwargs):
        self.commands.append(list(args))
        key = tuple(args)
        if key in self.returncodes:
            return self.returncodes[key]
        if args and args[0] == "omarchy-pkg-add":
            return self.returncodes.get(("omarchy-pkg-add", args[-1]), (0, ""))
        return 0, ""

    def admin(self, port):
        return False, False, False

    def spawn(self, args, output=None):
        self.commands.append(["spawn", *args])
        return 0


class AuditBackend(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="beam-audit-")
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.system = RecordingSystem()
        self.beam = beam.Beam(home=self.home, system=self.system, etc=self.home / "etc", proc=self.home / "proc")

    def test_qr_package_failure_does_not_install_sunshine(self):
        self.system.have_names = set()
        self.system.returncodes[("omarchy-pkg-add", "qrencode")] = (130, "")
        with patch.object(self.beam, "progress"), patch.object(self.beam, "repair") as repair:
            with self.assertRaises(beam.Failure) as raised:
                self.beam.perform("install")
        repair.assert_not_called()
        self.assertIn("QR helper", raised.exception.message)
        self.assertEqual([c for c in self.system.commands if c and c[0] == "omarchy-pkg-add"],
                         [["omarchy-pkg-add", "qrencode"]])

    def test_action_json_array_crashes_status_into_generic_failure(self):
        self.beam.state.mkdir(parents=True, exist_ok=True)
        (self.beam.state / "action.json").write_text("[]\n")
        with self.assertRaises(AttributeError):
            self.beam.action_state()
        with self.assertRaises(AttributeError):
            self.beam.status()

    def test_action_json_null_and_non_object_are_not_normalized(self):
        self.beam.state.mkdir(parents=True, exist_ok=True)
        for raw in ("null", "true", "1", '"busy"'):
            with self.subTest(raw=raw):
                (self.beam.state / "action.json").write_text(raw + "\n")
                with self.assertRaises(AttributeError):
                    self.beam.action_state()

    def test_opening_action_with_non_numeric_timestamp_crashes_status(self):
        self.beam.state.mkdir(parents=True, exist_ok=True)
        (self.beam.state / "action.json").write_text(json.dumps({
            "busy": True, "phase": "opening", "updatedAt": "now", "action": "install",
        }))
        with self.assertRaises(TypeError):
            self.beam.action_state()

    def test_fallback_status_omits_catalog_and_native_flags(self):
        data = beam.fallback_status()
        self.assertNotIn("ipadProfiles", data)
        self.assertNotIn("nativeResolution", data)
        self.assertNotIn("ipadProfile", data)
        self.assertNotIn("moonlightSetting", data)
        self.assertEqual(data["issues"][0]["code"], "probe")

    def test_log_json_non_object_is_not_caught_by_log_facts(self):
        log = self.home / "sunshine.log"
        now = dt.datetime.now().replace(microsecond=0)
        stamp = now.strftime("[%Y-%m-%d %H:%M:%S]")
        log.write_text(f"{stamp} Info: CLIENT CONNECTED\n")
        self.beam.cache.mkdir(parents=True, exist_ok=True)
        proc = dict(pid=123, identity="100", started=now.timestamp())
        (self.beam.cache / "log.json").write_text("null\n")
        with self.assertRaises(AttributeError):
            self.beam.log_facts([proc], log)

    def test_incomplete_cached_facts_raise_keyerror_on_connect_line(self):
        log = self.home / "sunshine.log"
        now = dt.datetime.now().replace(microsecond=0)
        stamp = now.strftime("[%Y-%m-%d %H:%M:%S]")
        log.write_text(f"{stamp} Info: CLIENT CONNECTED\n")
        self.beam.cache.mkdir(parents=True, exist_ok=True)
        proc = dict(pid=9, identity="50", started=now.timestamp())
        beam.atomic_json(self.beam.cache / "log.json", {
            "process": "9:50", "inode": log.stat().st_ino, "offset": 0,
            "facts": {"encoder": "libx264"},
        })
        with self.assertRaises(KeyError):
            self.beam.log_facts([proc], log)

    def test_duplicate_connected_then_disconnect_stays_streaming(self):
        log = self.home / "sunshine.log"
        now = dt.datetime.now().replace(microsecond=0)
        stamp = now.strftime("[%Y-%m-%d %H:%M:%S]")
        proc = dict(pid=3, identity="7", started=now.timestamp())
        log.write_text(
            f"{stamp} Info: CLIENT CONNECTED\n"
            f"{stamp} Info: CLIENT CONNECTED\n"
            f"{stamp} Info: CLIENT DISCONNECTED\n"
        )
        facts = self.beam.log_facts([proc], log)
        self.assertEqual(facts["streamCount"], 1)
        self.assertTrue(facts["streaming"])

    def test_pairing_root_returns_only_root_and_skips_disabled(self):
        path = self.home / "sunshine_state.json"
        path.write_text(json.dumps({
            "salt": "SHOULD-NOT-BE-READ",
            "username": "admin-hash-not-for-beam",
            "root": {
                "named_devices": [
                    {"uuid": "a", "cert": "cert-a", "enabled": False},
                    {"uuid": "b", "cert": "cert-b", "enabled": True},
                ],
                "devices": [{"uniqueid": "legacy", "certs": ["c"]}],
            },
        }))
        root = beam.pairing_root(path)
        self.assertEqual(set(root), {"named_devices", "devices"})
        self.assertEqual(beam.paired_count(root), 1)
        self.assertEqual(beam.legacy_paired_count(root), 1)
        dumped = json.dumps(root)
        self.assertNotIn("SHOULD-NOT-BE-READ", dumped)
        self.assertNotIn("admin-hash-not-for-beam", dumped)

    def test_username_in_conf_does_not_mark_admin_configured(self):
        self.beam.sun.mkdir(parents=True)
        (self.beam.sun / "sunshine.conf").write_text("username = already-created\nport = 47989\n")
        status = self.beam.status()
        self.assertFalse(status["adminConfigured"])
        self.assertFalse(status["adminUp"])

    def test_greet_lock_contention_does_not_write_marker(self):
        self.beam.state.mkdir(parents=True, exist_ok=True)
        barrier = threading.Barrier(2)
        held = threading.Event()

        def hold():
            with self.beam.lock():
                held.set()
                barrier.wait()
                barrier.wait()

        worker = threading.Thread(target=hold, daemon=True)
        worker.start()
        self.assertTrue(held.wait(2))
        with self.assertRaises(beam.Failure) as raised:
            self.beam.greet()
        self.assertIn("already running", raised.exception.message)
        self.assertFalse((self.beam.state / "greeted").exists())
        barrier.wait()
        worker.join(2)

    def test_open_admin_pin_path_stays_on_private_localhost(self):
        self.beam.status = lambda: dict(adminUp=True, adminUrl="https://localhost:48990")
        self.system.have_names.add("omarchy-launch-browser")
        with patch.object(self.system, "spawn", return_value=1) as spawn:
            pin = self.beam.open_admin(pin=True)
        self.assertTrue(pin["ok"])
        spawn.assert_called_with(["omarchy-launch-browser", "--private", "https://localhost:48990/pin"])


class AuditCatalog(unittest.TestCase):
    def test_catalog_has_45_models_17_groups_10_sizes(self):
        self.assertEqual(len(PROFILES), 17)
        models = [m["name"] for p in PROFILES for m in p["models"]]
        self.assertEqual(len(models), 45)
        self.assertEqual(len(set(models)), 45)
        sizes = {(p["width"], p["height"]) for p in PROFILES}
        self.assertEqual(len(sizes), 10)
        self.assertEqual(len({p["id"] for p in PROFILES}), 17)
        self.assertEqual({p["family"] for p in PROFILES}, {"iPad", "Air", "mini", "Pro"})
        self.assertTrue(all(profile(p["id"]) is p for p in PROFILES))
        public = profiles()
        self.assertTrue(all("models" not in row for row in public))
        self.assertEqual(len(public), 17)

    def test_every_catalog_size_has_a_defined_readable_scale(self):
        expected = {
            (2360, 1640): 2, (2160, 1620): 2, (2048, 1536): 2, (1024, 768): 1,
            (2732, 2048): 2, (2224, 1668): 2, (2266, 1488): 2, (2752, 2064): 2,
            (2420, 1668): 2, (2388, 1668): 2,
        }
        for width, height in expected:
            self.assertEqual(readable_scale(width, height), expected[(width, height)])
        self.assertEqual(readable_scale(2732, 2048), 2)
        logical = (2732 / (4 / 3), 2048 / (4 / 3))
        self.assertEqual(logical, (2049.0, 1536.0))


class AuditVirtual(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="beam-audit-v-")
        self.addCleanup(self.temp.cleanup)
        self.system = DisplaySystem()
        self.beam = beam.Beam(home=Path(self.temp.name), system=self.system)
        self.fit = self.beam.display
        self.v = self.fit.virtual
        self.physical = dict(self.system.monitors[0], id=0, mirrorOf="none",
                             activeWorkspace=dict(id=1, name="1"))
        self.virtual = dict(self.physical, name=OUTPUT, id=1, width=2048, height=1536,
                            scale=2, x=8000, activeWorkspace=dict(id=-1337, name="beam-idle"))
        self.rows = [self.physical, self.virtual]
        self.spaces = [dict(id=1, name="1", monitor="DP-1"),
                       dict(id=-1337, name="beam-idle", monitor=OUTPUT)]
        self.v.monitors = lambda: copy.deepcopy(self.rows)
        self.v.workspaces = lambda: copy.deepcopy(self.spaces)
        self.v.command = lambda code: None
        self.v.focus = lambda *args, **kwargs: None

        def apply(name, mode):
            row = next(m for m in self.rows if m["name"] == name)
            row.update({k: mode[k] for k in ["width", "height", "refreshRate", "x", "y", "scale", "transform"]})
            if "mirror" in mode:
                row["mirrorOf"] = (str(next(m["id"] for m in self.rows if m["name"] == mode["mirror"]))
                                   if mode["mirror"] else "none")

        self.fit.apply = apply

        def move(workspace, monitor):
            next(space for space in self.spaces if space["id"] == workspace["id"])["monitor"] = monitor

        self.v.move = move
        self.beam.processes = lambda: [dict(pid=123, identity="456")]
        save(self.v.preferences, dict(entry=str(self.beam.entry), output=OUTPUT))

    def start(self, width=2732, height=2048):
        return self.fit.start({
            "SUNSHINE_CLIENT_WIDTH": str(width),
            "SUNSHINE_CLIENT_HEIGHT": str(height),
            "SUNSHINE_CLIENT_FPS": "60",
        })

    def test_missing_virtual_output_clears_recovery_while_leaving_mirror(self):
        self.start()
        self.assertEqual(self.physical["mirrorOf"], "1")
        self.rows.remove(self.virtual)
        restored = self.fit.stop()
        self.assertTrue(restored)
        self.assertEqual(self.physical["mirrorOf"], "1")
        self.assertFalse(load(self.fit.state))

    def test_plugin_path_change_wipes_saved_ipad_and_custom_scale(self):
        self.fit.set_resolution("2732x2048", 4 / 3)
        self.fit.select_ipad("air-2732")
        self.assertEqual(self.fit.fixed_scale(), 4 / 3)
        self.assertEqual(self.fit.status()["ipadProfile"], "air-2732")
        save(self.v.preferences, dict(entry="/old/plugin/bin/omarchy-beam", output=OUTPUT))
        self.assertTrue(self.v.install())
        self.assertIsNone(self.fit.fixed_size())
        self.assertEqual(self.fit.status()["ipadProfile"], "")
        self.assertEqual(load(self.v.preferences)["entry"], str(self.beam.entry))

    def test_remove_unlinks_prefs_after_failed_output_delete(self):
        self.assertTrue(any(m["name"] == OUTPUT for m in self.rows))
        self.v.remove()
        self.assertFalse(self.v.enabled())
        self.assertTrue(any(m["name"] == OUTPUT for m in self.rows))
        with self.assertRaises(DisplayError) as raised:
            self.v.install()
        self.assertIn("already uses Beam's capture name", raised.exception.message)

    def test_remove_skips_headless_output_when_prefs_are_missing(self):
        self.v.preferences.unlink()
        self.v.remove()
        self.assertTrue(any(m["name"] == OUTPUT for m in self.rows))

    def test_falsy_virtual_prefs_resize_the_physical_panel(self):
        self.v.preferences.write_text("[]\n")
        session = self.fit.start({
            "SUNSHINE_CLIENT_WIDTH": "2048",
            "SUNSHINE_CLIENT_HEIGHT": "1536",
            "SUNSHINE_CLIENT_FPS": "60",
        })
        self.assertNotEqual(session.get("kind"), "virtual")
        self.assertEqual(self.physical["width"], 1024)
        self.assertEqual(self.physical["name"], "DP-1")

    def test_corrupt_session_hides_native_resolution_from_status(self):
        self.fit.select_ipad("air-2732")
        self.assertTrue(self.v.enabled())
        self.fit.state.write_text("null\n")
        status = self.fit.status()
        self.assertFalse(status.get("nativeResolution"))
        self.assertEqual(status["ipadProfile"], "")
        self.assertTrue(self.v.enabled())
        self.assertEqual(self.fit.fixed_size(), (2732, 2048, 60))

    def test_json_array_session_does_not_restore_and_physical_start_crashes(self):
        self.fit.state.write_text("[1]\n")
        with self.assertRaises(AttributeError):
            self.fit.start({
                "SUNSHINE_CLIENT_WIDTH": "2732",
                "SUNSHINE_CLIENT_HEIGHT": "2048",
                "SUNSHINE_CLIENT_FPS": "60",
            })
        self.assertEqual(self.physical["width"], 5120)

    def test_same_size_reselect_keeps_four_thirds_for_user_ipad(self):
        self.fit.set_resolution("2732x2048", 4 / 3)
        self.fit.select_ipad("pro-2732")
        self.fit.select_ipad("air-2732")
        session = self.start(2732, 2048)
        applied = session["applied"]
        self.assertEqual((applied["width"], applied["height"]), (2732, 2048))
        self.assertEqual(applied["scale"], 4 / 3)
        self.assertEqual((applied["width"] / applied["scale"], applied["height"] / applied["scale"]),
                         (2049.0, 1536.0))
        self.fit.stop(session["token"])
        self.assertEqual(self.physical["width"], 5120)
        self.assertEqual(self.physical["scale"], 1)
        self.assertEqual(self.fit.fixed_scale(), 4 / 3)


class AuditDisplay(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="beam-audit-d-")
        self.addCleanup(self.folder.cleanup)
        self.system = DisplaySystem()
        self.beam = beam.Beam(home=Path(self.folder.name), system=self.system)
        self.beam.processes = lambda: [dict(pid=234, identity="567")]
        self.fit = self.beam.display

    def test_load_null_session_is_not_an_empty_dict(self):
        self.fit.state.parent.mkdir(parents=True, exist_ok=True)
        self.fit.state.write_text("null")
        self.assertIsNone(load(self.fit.state))
        status = self.fit.status()
        self.assertNotIn("nativeResolution", status)
        self.assertFalse(status["resolutionReady"])

    def test_original_mode_string_uses_five_decimals_not_advertised_text(self):
        original = self.fit.original(self.system.monitors[0])
        self.assertEqual(original["mode"], "5120x1440@59.97700")
        self.assertNotIn(original["mode"], self.system.monitors[0]["availableModes"])
        self.assertNotIn(original["mode"] + "Hz", self.system.monitors[0]["availableModes"])


class AuditAstAndUi(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_no_password_argv_or_sudo_stdin_handling(self):
        source = (self.ROOT / "lib/beam.py").read_text()
        tree = ast.parse(source)
        joined = ast.dump(tree)
        self.assertNotIn("getpass", joined)
        self.assertNotIn("SUDO_ASKPASS", source)
        self.assertNotIn("password=", source.lower())
        self.assertIn('["sudo", "env", "PATH=/usr/bin"', source)
        self.assertIn("Never handle", (self.ROOT / "CLAUDE.md").read_text() + source)

    def test_service_qml_greet_is_one_shot_and_terminal_is_silent_when_busy(self):
        text = (self.ROOT / "Service.qml").read_text()
        self.assertIn('Timer { interval: 4000; running: true; onTriggered: root.run(["greet"]) }', text)
        self.assertNotIn("repeat: true; onTriggered: root.run([\"greet\"])", text)
        self.assertIn("if (busy || pending.some(function(args) { return args[0] === \"terminal\" })) return", text)

    def test_panel_has_no_scroll_container(self):
        for name in ("BeamPanel.qml", "Service.qml", "BarWidget.qml", "QrCode.qml"):
            text = (self.ROOT / name).read_text()
            self.assertNotIn("Flickable", text)
            self.assertNotIn("ScrollView", text)

    def test_browser_rejects_userinfo_and_rewrites_loopback_to_localhost(self):
        from beam_browser import browser_command
        self.assertEqual(
            browser_command(["https://127.0.0.1:47990/pin"], 47990, True),
            ["omarchy-launch-browser", "--private", "https://localhost:47990/pin"],
        )
        self.assertEqual(
            browser_command(["https://localhost:47990@evil.test/pin"], 47990, True),
            ["/usr/bin/xdg-open", "https://localhost:47990@evil.test/pin"],
        )


if __name__ == "__main__":
    unittest.main()
