"""Terminal/action state races, undo refusal paths, install idempotency, admin_port dup keys."""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / "lib"))

from audit_helpers import load_beam, FakeSystem
from beam_browser import admin_port

beam = load_beam()


class ActionStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.system = FakeSystem(present={"omarchy-launch-terminal"})
        self.beam = beam.Beam(home=self.home, system=self.system, etc=self.home / "etc")

    def terminal(self, action):
        with patch.object(self.system, "spawn", create=True):
            return self.beam.terminal(action)

    def test_pending_then_stale_then_reopen(self):
        first = self.terminal("ports")
        self.assertTrue(first["busy"])
        self.assertEqual(self.beam.action_state()["phase"], "opening")
        second = self.terminal("undo")
        self.assertFalse(second["ok"])  # already open
        saved = json.loads((self.beam.state / "action.json").read_text())
        saved["updatedAt"] = time.time() * 1000 - 21000
        (self.beam.state / "action.json").write_text(json.dumps(saved))
        stale = self.beam.action_state()
        self.assertFalse(stale["busy"])
        self.assertEqual(stale["state"], "error")
        self.assertEqual(stale["retryAction"], "ports")
        self.assertEqual(stale["id"], first["id"])
        reopened = self.terminal("repair")
        self.assertTrue(reopened["busy"])
        self.assertNotEqual(reopened["id"], first["id"])

    def test_dead_action_pid_is_reported_as_interrupted(self):
        pending = self.terminal("install")
        saved = json.loads((self.beam.state / "action.json").read_text())
        saved.update(phase="running", pid=999999, identity="12345")
        (self.beam.state / "action.json").write_text(json.dumps(saved))
        state = self.beam.action_state()
        self.assertEqual(state["state"], "error")
        self.assertIn("closed before finishing", state["message"])

    def test_execute_requires_tty_and_refuses_root(self):
        result = self.beam.execute("repair")
        self.assertFalse(result["ok"])
        self.assertIn("visible setup terminal", result["message"])
        with patch.object(beam.os, "geteuid", return_value=0):
            self.assertFalse(beam.Beam(home=self.home, system=self.system).execute("repair")["ok"])

    def test_spawn_failure_is_written_as_error_result(self):
        with patch.object(self.system, "spawn", create=True, side_effect=OSError("no terminal")):
            result = self.beam.terminal("install")
        self.assertFalse(result["ok"])
        saved = json.loads((self.beam.state / "action.json").read_text())
        self.assertFalse(saved["busy"])


class UndoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.system = FakeSystem()
        self.beam = beam.Beam(home=self.home, system=self.system, etc=self.home / "etc")
        self.beam.units = lambda: []
        self.beam.stop_processes = lambda rows, retry="repair": None
        self.beam.processes = lambda name="sunshine": []
        self.beam.firewall = lambda: {"ufwRules": 0}
        self.beam.display.stop = lambda token=None: None
        self.beam.display.virtual.remove = lambda: None

    def perform(self):
        with patch.object(self.beam, "progress"):
            return self.beam.perform("undo")

    def test_symlinked_config_is_never_followed(self):
        real = self.home / "real-config"
        real.mkdir()
        self.beam.sun.parent.mkdir(parents=True, exist_ok=True)
        self.beam.sun.symlink_to(real)
        with self.assertRaises(beam.Failure):
            self.perform()
        self.assertTrue(self.beam.sun.is_symlink())
        self.assertTrue(real.exists())

    def test_leftover_package_fails_truthfully(self):
        self.beam.sun.mkdir(parents=True)
        self.system.present.add("sunshine")
        with self.assertRaises(beam.Failure) as ctx:
            self.perform()
        self.assertEqual(ctx.exception.retry, "undo")

    def test_clean_undo_removes_config_and_browser_marker(self):
        self.beam.sun.mkdir(parents=True)
        self.beam.browser.install()
        self.assertTrue(self.beam.browser.ready())
        result = self.perform()
        self.assertTrue(result["ok"])
        self.assertFalse(self.beam.sun.exists())
        autostart = self.home / ".config/hypr/autostart.lua"
        if autostart.exists():
            self.assertNotIn("beam-sunshine-browser", autostart.read_text())


class InstallIdempotencyTests(unittest.TestCase):
    def test_second_install_skips_packages_and_repairs(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        system = FakeSystem()
        b = beam.Beam(home=Path(temp.name), system=system)
        installed = {"sunshine", "qrencode"}
        system.present = installed
        with patch.object(b, "progress"), patch.object(b, "repair") as repair:
            result = b.perform("install")
        self.assertTrue(result["ok"])
        # qrencode is re-added every time (observable, harmless no-op), but the
        # sunshine package must not be reinstalled once present.
        self.assertNotIn(["omarchy-pkg-add", "sunshine"], system.commands)
        repair.assert_called_once()

    def test_qr_cancel_stops_before_any_sunshine_change(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        system = FakeSystem(responses={("omarchy-pkg-add", "qrencode"): (130, "")})
        b = beam.Beam(home=Path(temp.name), system=system)
        with patch.object(b, "progress"), patch.object(b, "repair") as repair:
            with self.assertRaises(beam.Failure) as ctx:
                b.perform("install")
        self.assertEqual(ctx.exception.retry, "install")
        repair.assert_not_called()
        self.assertEqual(system.commands, [["omarchy-pkg-add", "qrencode"]])


class AdminPortTests(unittest.TestCase):
    def test_duplicate_port_keys_first_wins_vs_config_values_last_wins(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        config = Path(temp.name)
        (config / "sunshine").mkdir()
        (config / "sunshine/sunshine.conf").write_text("port = 47989\nport = 48000\n")
        with patch.dict(os.environ, XDG_CONFIG_HOME=str(config)):
            # BUG: admin_port returns on the FIRST key while beam.config_values
            # keeps the LAST. Duplicate port lines make Beam's admin URL and the
            # rest of its config handling disagree.
            self.assertEqual(admin_port(), 47990)
        b = beam.Beam(home=Path(temp.name) / "home", system=FakeSystem())
        b.config = config
        b.sun = config / "sunshine"
        self.assertEqual(b.config_values()["port"], "48000")


if __name__ == "__main__":
    unittest.main()
