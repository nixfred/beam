"""Resolution selection and recovery use synthetic displays, never host output."""
import copy
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("beam", Path(__file__).parents[1] / "lib/beam.py")
beam = importlib.util.module_from_spec(spec)
spec.loader.exec_module(beam)
from beam_display import APP_NAME, DisplayError, choose_mode, load, requested_size, save


class DisplaySystem:
    def __init__(self):
        self.monitors = [dict(name="DP-1", width=5120, height=1440, refreshRate=59.977,
                              x=1600, y=0, scale=1, transform=0,
                              availableModes=["5120x1440@59.98Hz", "2560x1440@59.95Hz",
                                              "1920x1080@60.00Hz", "1280x1024@60.02Hz", "1024x768@60.00Hz"])]
        self.commands = []
        self.before_apply = lambda: None

    def run(self, args, **_):
        self.commands.append(args)
        if args == ["hyprctl", "-j", "monitors"]:
            return 0, json.dumps(self.monitors)
        if args[:2] == ["hyprctl", "eval"]:
            self.before_apply()
            name, w, h, hz, x, y, scale = re.fullmatch(
                r'hl.monitor\(\{ output = "([\w-]+)", mode = "(\d+)x(\d+)@([\d.]+)", position = "(-?\d+)x(-?\d+)", scale = ([\d.]+) \}\)', args[2]).groups()
            m = next(m for m in self.monitors if m["name"] == name)
            m.update(width=int(w), height=int(h), refreshRate=float(hz), x=int(x), y=int(y), scale=float(scale))
            return 0, "ok\n"
        return 1, ""


class DisplayTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.system = DisplaySystem()
        self.beam = beam.Beam(home=Path(self.folder.name), system=self.system)
        self.beam.processes = lambda: [dict(pid=234, identity="567")]
        self.fit = self.beam.display
        self.request = {"SUNSHINE_CLIENT_WIDTH": "2048", "SUNSHINE_CLIENT_HEIGHT": "1536", "SUNSHINE_CLIENT_FPS": "60"}

    def test_ultrawide_becomes_ipad_aspect_without_exceeding_client(self):
        mode = choose_mode(self.system.monitors[0], (2048, 1536, 60))
        self.assertEqual((mode["width"], mode["height"]), (1024, 768))
        self.assertFalse(mode["exact"])

    def test_exact_native_mode_wins_when_advertised(self):
        self.system.monitors[0]["availableModes"] += ["2048x1536@60.00Hz"]
        self.assertTrue(choose_mode(self.system.monitors[0], (2048, 1536, 60))["exact"])

    def test_rotated_output_keeps_native_mode_and_reports_picture_dimensions(self):
        self.system.monitors[0]["transform"] = 1
        session = self.fit.start(dict(self.request, SUNSHINE_CLIENT_WIDTH="1536", SUNSHINE_CLIENT_HEIGHT="2048"))
        self.assertEqual(session["applied"]["mode"], "1024x768@60")
        self.assertIn("768×1024", self.fit.status()["resolutionDetail"])
        self.fit.stop()
        self.assertEqual(self.system.monitors[0]["width"], 5120)
        self.assertEqual(self.system.monitors[0]["transform"], 1)

    def test_16_by_9_request_uses_1080p_instead_of_ultrawide(self):
        self.assertEqual(choose_mode(self.system.monitors[0], (1920, 1080, 60))["mode"], "1920x1080@60")

    def test_unavailable_size_fails_without_applying_a_modeline(self):
        with self.assertRaises(DisplayError):
            choose_mode(self.system.monitors[0], (400, 400, 60))
        self.assertFalse(self.system.commands)

    def test_fixed_1440p_overrides_720p_desktop_but_reports_client_request(self):
        self.fit.set_resolution("2560x1440")
        session = self.fit.start(dict(self.request, SUNSHINE_CLIENT_WIDTH="1280", SUNSHINE_CLIENT_HEIGHT="720"))
        self.assertEqual(session["requested"], [1280, 720, 60])
        self.assertEqual(session["target"], [2560, 1440, 60])
        self.assertEqual(self.system.monitors[0]["width"], 2560)
        self.assertIn("Moonlight requests 1280×720", self.fit.status()["resolutionDetail"])
        self.assertEqual(self.fit.status()["moonlightSetting"], "Custom 2560×1440")

    def test_fixed_size_restores_original_scale_and_persists_for_next_stream(self):
        self.system.monitors[0]["scale"] = 2
        self.fit.set_resolution("2560x1440")
        self.fit.start(self.request)
        self.assertEqual(self.system.monitors[0]["scale"], 1)
        self.fit.stop()
        self.assertEqual(self.system.monitors[0]["width"], 5120)
        self.assertEqual(self.system.monitors[0]["scale"], 2)
        self.assertEqual(self.fit.fixed_size(), (2560, 1440, 60))

    def test_unsupported_fixed_mode_preserves_previous_setting(self):
        self.fit.set_resolution("1920x1080")
        with self.assertRaises(DisplayError):
            self.fit.set_resolution("2752x2064")
        self.assertEqual(self.fit.fixed_size(), (1920, 1080, 60))
        self.assertEqual(self.system.monitors[0]["width"], 5120)

    def test_auto_clears_fixed_mode_and_follows_client_again(self):
        self.fit.set_resolution("2560x1440")
        self.fit.set_resolution("auto")
        self.fit.start(dict(self.request, SUNSHINE_CLIENT_WIDTH="1920", SUNSHINE_CLIENT_HEIGHT="1080"))
        self.assertEqual(self.system.monitors[0]["width"], 1920)
        self.assertFalse(self.fit.status()["resolutionPinned"])

    def test_disappearing_fixed_mode_fails_instead_of_silently_shrinking(self):
        self.fit.set_resolution("2560x1440")
        self.system.monitors[0]["availableModes"] = ["1920x1080@60Hz"]
        with self.assertRaises(DisplayError):
            self.fit.start(self.request)
        self.assertEqual(self.system.monitors[0]["width"], 5120)
        self.assertFalse(self.fit.state.exists())

    def test_matching_fixed_request_is_reported_without_mismatch(self):
        self.fit.set_resolution("2560x1440")
        self.fit.start(dict(self.request, SUNSHINE_CLIENT_WIDTH="2560", SUNSHINE_CLIENT_HEIGHT="1440"))
        self.assertIn("Moonlight matches", self.fit.status()["resolutionDetail"])

    def test_client_mismatch_survives_disconnect_and_matching_reconnect_clears_it(self):
        self.fit.set_resolution("2560x1440")
        self.fit.start(dict(self.request, SUNSHINE_CLIENT_WIDTH="1280", SUNSHINE_CLIENT_HEIGHT="720",
                            PRIVATE_VALUE="must not be saved"))
        self.fit.stop()
        self.assertFalse(self.fit.status()["resolutionActive"])
        self.assertIn("Last stream requested 1280×720; set Custom 2560×1440", self.fit.status()["resolutionDetail"])
        self.assertEqual(load(self.fit.last_request), dict(SUNSHINE_CLIENT_WIDTH=1280,
                         SUNSHINE_CLIENT_HEIGHT=720, SUNSHINE_CLIENT_FPS=60))
        self.fit.start(dict(self.request, SUNSHINE_CLIENT_WIDTH="2560", SUNSHINE_CLIENT_HEIGHT="1440"))
        self.fit.stop()
        self.assertNotIn("Last stream requested", self.fit.status()["resolutionDetail"])

    def test_missing_or_corrupt_last_request_does_not_break_readiness(self):
        self.fit.install()
        self.fit.set_resolution("2560x1440")
        for contents in (None, "{broken", '[]', '{"SUNSHINE_CLIENT_WIDTH": "invalid"}'):
            with self.subTest(contents=contents):
                if contents is not None:
                    self.fit.last_request.write_text(contents)
                self.assertTrue(self.fit.status()["resolutionReady"])
                self.assertNotIn("Last stream requested", self.fit.status()["resolutionDetail"])

    def test_client_dimensions_are_validated_as_numbers(self):
        for value in ("$(touch /tmp/should-never-exist)", "0", "-1", "999999", "nan"):
            with self.subTest(value=value), self.assertRaises(DisplayError):
                requested_size(dict(self.request, SUNSHINE_CLIENT_WIDTH=value))
        with self.assertRaises(DisplayError):
            requested_size({})

    def test_app_install_is_idempotent_and_preserves_other_apps(self):
        original = {"env": {"EXAMPLE": "value"}, "apps": [{"name": "Custom", "cmd": "game", "prep-cmd": [{"do": "custom"}]}]}
        save(self.fit.app_path(), original)
        self.assertTrue(self.fit.install())
        self.assertFalse(self.fit.install())
        data = load(self.fit.app_path())
        self.assertEqual(data["apps"][0], original["apps"][0])
        self.assertEqual(data["env"], original["env"])
        self.assertEqual(data["apps"][1]["name"], APP_NAME)
        self.assertTrue(self.fit.status()["resolutionReady"])

    def test_unowned_app_collision_is_not_overwritten(self):
        original = {"apps": [{"name": APP_NAME, "cmd": "my-own-app"}]}
        save(self.fit.app_path(), original)
        with self.assertRaises(DisplayError):
            self.fit.install()
        self.assertEqual(load(self.fit.app_path()), original)

    def test_stock_desktop_also_runs_resize_and_recovery(self):
        original = {"env": {}, "apps": [{"name": "Desktop", "image-path": "desktop.png"}, self.fit.app()]}
        save(self.fit.app_path(), original)
        self.assertFalse(self.fit.status()["resolutionReady"])
        self.assertTrue(self.fit.install())
        apps = load(self.fit.app_path())["apps"]
        self.assertEqual(apps[0], dict(apps[1], name="Desktop"))
        self.assertIn("stream-start", apps[0]["prep-cmd"][0]["do"])
        self.assertIn("stream-stop", apps[0]["prep-cmd"][0]["undo"])
        self.assertFalse(self.fit.install())
        self.assertTrue(self.fit.status()["resolutionReady"])
        backups = list(self.beam.state.glob("apps-before-sizing-*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(load(backups[0]), original)

    def test_custom_desktop_commands_and_settings_are_preserved(self):
        for custom in ({"name": "Desktop", "cmd": "my-desktop"},
                       {"name": "Desktop", "prep-cmd": [{"do": "custom"}]},
                       {"name": "Desktop", "image-path": "custom.png"},
                       {"name": "Desktop", "exclude-global-prep-cmd": True}):
            with self.subTest(custom=custom):
                save(self.fit.app_path(), {"apps": [custom]})
                self.fit.install()
                self.assertEqual(load(self.fit.app_path())["apps"][0], custom)
                self.assertTrue(self.fit.status()["resolutionReady"])

    def test_ambiguous_desktop_names_are_preserved(self):
        apps = [{"name": "Desktop"}, {"name": "Desktop", "cmd": "custom"}]
        save(self.fit.app_path(), {"apps": apps})
        self.fit.install()
        self.assertEqual(load(self.fit.app_path())["apps"][:2], apps)

    def test_corrupt_app_config_is_not_overwritten(self):
        self.fit.app_path().parent.mkdir(parents=True)
        self.fit.app_path().write_text("{broken")
        with self.assertRaises(DisplayError):
            self.fit.install()
        self.assertEqual(self.fit.app_path().read_text(), "{broken")

    def test_snapshot_precedes_resize_and_original_geometry_is_restored(self):
        original = copy.deepcopy(self.system.monitors[0])
        self.system.before_apply = lambda: self.assertEqual(load(self.fit.state)["original"]["width"], 5120)
        session = self.fit.start(self.request)
        self.assertEqual(self.system.monitors[0]["width"], 1024)
        self.assertEqual(self.system.monitors[0]["x"], 1600)
        self.fit.stop(session["token"])
        self.assertEqual(self.system.monitors[0], original)
        self.assertFalse(self.fit.state.exists())

    def test_failed_resize_rolls_back_and_clears_recovery_state(self):
        apply = self.fit.apply
        calls = []
        def fail_once(name, mode):
            calls.append(mode)
            if len(calls) == 1:
                raise DisplayError("simulated modeset failure")
            return apply(name, mode)
        with patch.object(self.fit, "apply", side_effect=fail_once), self.assertRaises(DisplayError):
            self.fit.start(self.request)
        self.assertEqual(self.system.monitors[0]["width"], 5120)
        self.assertFalse(self.fit.state.exists())

    def test_failed_restore_keeps_recovery_state_for_retry(self):
        self.fit.start(self.request)
        with patch.object(self.fit, "apply", side_effect=DisplayError("retry needed")), self.assertRaises(DisplayError):
            self.fit.stop()
        self.assertIn("Restore display", load(self.fit.state)["error"])
        self.fit.stop()
        self.assertEqual(self.system.monitors[0]["width"], 5120)

    def test_manual_display_changes_are_preserved(self):
        self.fit.start(self.request)
        self.system.monitors[0].update(width=1920, height=1080)
        self.fit.stop()
        self.assertEqual(self.system.monitors[0]["width"], 1920)

    def test_old_session_cannot_restore_a_new_session(self):
        self.fit.start(self.request)
        self.fit.stop("expired-token")
        self.assertEqual(self.system.monitors[0]["width"], 1024)
        self.assertTrue(self.fit.state.exists())

    def test_multiple_displays_require_unambiguous_capture_selection(self):
        self.system.monitors.append(dict(self.system.monitors[0], name="DP-2"))
        with self.assertRaises(DisplayError):
            self.fit.start(self.request)
        self.beam.sun.mkdir(parents=True)
        (self.beam.sun / "sunshine.conf").write_text("output_name = DP-2\n")
        self.fit.start(self.request)
        self.assertEqual(self.system.monitors[0]["width"], 5120)
        self.assertEqual(self.system.monitors[1]["width"], 1024)

    def test_sunshine_crash_restores_original_display(self):
        self.fit.start(self.request)
        self.beam.processes = lambda: []
        self.fit.supervise()
        self.assertEqual(self.system.monitors[0]["width"], 5120)

    def test_monitor_change_ends_session_and_preserves_new_layout(self):
        self.fit.start(self.request)
        self.system.monitors[0].update(width=1920, height=1080)
        self.fit.supervise()
        self.assertEqual(self.system.monitors[0]["width"], 1920)
        self.assertFalse(self.fit.state.exists())

    def test_disconnect_ends_foreground_app_and_restores_display(self):
        self.fit.start(self.request)
        self.beam.log_facts = lambda *args: {"streaming": next(events)}
        events = iter([True, False])
        with patch("beam_display.time.monotonic", side_effect=[0, 1, 5, 6, 6]), patch("beam_display.time.sleep"):
            self.fit.supervise()
        self.assertEqual(self.system.monitors[0]["width"], 5120)


if __name__ == "__main__":
    unittest.main()
