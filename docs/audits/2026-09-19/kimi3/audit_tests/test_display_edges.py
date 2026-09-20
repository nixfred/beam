"""Physical display edges: corrupt session status, duplicate apps, supervise token changes."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / "tests"))

from audit_helpers import load_beam
from test_display import DisplaySystem
from beam_display import APP_NAME, DisplayError, choose_mode, load, requested_size, save

beam = load_beam()


class DisplayEdgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.system = DisplaySystem()
        self.beam = beam.Beam(home=Path(self.temp.name), system=self.system)
        self.beam.processes = lambda: [dict(pid=234, identity="567")]
        self.fit = self.beam.display
        self.request = {"SUNSHINE_CLIENT_WIDTH": "2048", "SUNSHINE_CLIENT_HEIGHT": "1536",
                        "SUNSHINE_CLIENT_FPS": "60"}

    def test_corrupt_session_file_degrades_status_without_hiding_readiness_cause(self):
        self.fit.install()
        self.fit.state.parent.mkdir(parents=True, exist_ok=True)
        self.fit.state.write_text('{"token": "abc", "applied": {}, "requested": [1, 2, 3]}')
        status = self.fit.status()
        # corrupt session entries trigger KeyError; status degrades wholesale
        self.assertFalse(status["resolutionReady"])

    def test_duplicate_beam_apps_make_status_not_ready_and_repair_fails(self):
        save(self.fit.app_path(), {"apps": [self.fit.app(), self.fit.app()]})
        self.assertFalse(self.fit.status()["resolutionReady"])
        with self.assertRaises(DisplayError):
            self.fit.install()

    def test_choose_mode_rejects_bad_mode_strings_and_extreme_rates(self):
        monitor = dict(self.system.monitors[0])
        monitor["availableModes"] = ["garbage", "2048x1536", "2048x1536@500Hz",
                                     "2048x1536@10Hz", "2048x1536@abc", "0x0@60Hz",
                                     "2048x1536@60.00Hz"]
        mode = choose_mode(monitor, (2048, 1536, 60))
        self.assertEqual(mode["mode"], "2048x1536@60")

    def test_requested_size_boundaries(self):
        for value, ok in ((320, True), (319, False), (8192, True), (8193, False)):
            with self.subTest(value=value):
                env = {"SUNSHINE_CLIENT_WIDTH": str(value), "SUNSHINE_CLIENT_HEIGHT": "320",
                       "SUNSHINE_CLIENT_FPS": "60"}
                try:
                    requested_size(env)
                    self.assertTrue(ok)
                except DisplayError:
                    self.assertFalse(ok)
        with self.assertRaises(DisplayError):  # pixel budget
            requested_size({"SUNSHINE_CLIENT_WIDTH": "8192", "SUNSHINE_CLIENT_HEIGHT": "8192",
                            "SUNSHINE_CLIENT_FPS": "60"})
        with self.assertRaises(DisplayError):  # fps bounds
            requested_size({"SUNSHINE_CLIENT_WIDTH": "2048", "SUNSHINE_CLIENT_HEIGHT": "1536",
                            "SUNSHINE_CLIENT_FPS": "241"})

    def test_supervise_with_superseded_token_does_not_restore_new_session(self):
        first = self.fit.start(self.request)
        self.fit.stop()
        second = self.fit.start(self.request)
        # stale supervisor from the first app instance exits via token mismatch
        self.fit.stop(first["token"])
        self.assertTrue(load(self.fit.state))
        self.fit.stop(second["token"])
        self.assertFalse(load(self.fit.state))

    def test_fixed_scale_out_of_range_workspace_falls_back_to_one(self):
        # a fixed mode whose scale would shrink the workspace below minimum
        self.system.monitors[0]["availableModes"] += ["1280x1024@60.00Hz"]
        with self.assertRaises(DisplayError):  # 640x512 workspace < 960x640
            self.fit.set_resolution("1280x1024", 2)
        self.assertIsNone(self.fit.fixed_size())

    def test_incomplete_session_json_crashes_with_key_error_not_display_error(self):
        self.fit.state.parent.mkdir(parents=True, exist_ok=True)
        self.fit.state.write_text('{"token": "abc", "applied": {}, "requested": [1, 2, 3]}')
        # BUG: a structurally valid but incomplete session file raises a raw
        # KeyError ("monitor") out of start()/stop() instead of a DisplayError
        # with recovery guidance. main() maps it to a generic failure.
        with self.assertRaises(KeyError):
            self.fit.start(self.request)
        with self.assertRaises(KeyError):
            self.fit.stop()

    def test_status_fixed_detail_uses_last_request_only_when_mismatched(self):
        self.fit.set_resolution("2560x1440")
        self.fit.start(dict(self.request, SUNSHINE_CLIENT_WIDTH="2560", SUNSHINE_CLIENT_HEIGHT="1440"))
        self.fit.stop()
        self.assertNotIn("Last stream requested", self.fit.status()["resolutionDetail"])


if __name__ == "__main__":
    unittest.main()
