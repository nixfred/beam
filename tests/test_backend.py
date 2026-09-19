"""Backend regressions use synthetic files and commands, never host setup."""
import datetime as dt
import importlib.util
from pathlib import Path
import tempfile
import sys
import time
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("beam", Path(__file__).parents[1] / "lib/beam.py")
beam = importlib.util.module_from_spec(spec)
spec.loader.exec_module(beam)


class FakeSystem:
    def __init__(self):
        self.commands = []
        self.firewall_output = "Status: active\n"

    def have(self, name):
        return name == "ufw"

    def run(self, args, **kwargs):
        self.commands.append(args)
        if args == ["sudo", "-n", "ufw", "status"]:
            return 0, self.firewall_output
        return 0, ""


class BackendTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.system = FakeSystem()
        self.beam = beam.Beam(home=self.home, system=self.system, etc=self.home / "etc")

    def test_one_firewall_rule_is_not_complete_setup(self):
        self.system.firewall_output += "47984/tcp ALLOW IN 10.0.0.0/8 # omarchy-sunshine\n"
        status = self.beam.firewall()
        self.assertEqual(status["ufwRules"], 1)
        self.assertFalse(status["firewallReady"])
        self.assertEqual(status["firewallState"], "incomplete")

    def test_complete_lan_rules_and_inactive_firewall_are_ready(self):
        for proto, ports in beam.PORTS.items():
            for port in ports:
                for cidr in beam.PRIVATE_CIDRS:
                    self.system.firewall_output += f"{port}/{proto} ALLOW IN {cidr} # omarchy-sunshine\n"
        self.assertTrue(self.beam.firewall()["firewallReady"])
        self.system.firewall_output = "Status: inactive\n"
        self.assertTrue(self.beam.firewall()["firewallReady"])

    def test_welcome_is_once_and_uses_the_beam_panel_route(self):
        self.beam.status = lambda: {"ready": False}
        self.assertTrue(self.beam.greet()["ok"])
        self.assertTrue(self.beam.greet()["ok"])
        notifications = [c for c in self.system.commands if c[0] == "omarchy-notification-send"]
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0][-4:], ["--exec", "omarchy-shell", "nixfred.beam", "open"])

    def test_stream_state_tracks_current_process_and_complete_log_lines(self):
        log = self.home / "sunshine.log"
        now = dt.datetime.now().replace(microsecond=0)
        stamp = now.strftime("[%Y-%m-%d %H:%M:%S]")
        proc = dict(pid=123, identity="100", started=now.timestamp())
        log.write_text(f"{stamp} Info: Found H.264 encoder: libx264\n"
                       f"{stamp} Info: Found display\n"
                       f"{stamp} Info: CLIENT CONNECTED\n"
                       f"{stamp} Info: CLIENT DISCON")
        status = self.beam.log_facts([proc], log)
        self.assertEqual(status["encoder"], "libx264")
        self.assertTrue(status["displayFound"])
        self.assertTrue(status["streaming"])
        with log.open("a") as stream:
            stream.write("NECTED\n")
        self.assertFalse(self.beam.log_facts([proc], log)["streaming"])
        self.assertFalse(self.beam.log_facts([], log)["streaming"])
        later = dict(proc, identity="200", started=now.timestamp() + 60)
        restarted = self.beam.log_facts([later], log)
        self.assertEqual(restarted["encoder"], "")
        self.assertFalse(restarted["displayFound"])

    def test_exited_child_does_not_block_removal_while_parent_terminal_is_open(self):
        proc = self.home / "proc"
        (proc / "123").mkdir(parents=True)
        (proc / "123/stat").write_text("123 (sunshine) Z " + "0 " * 18 + "100\n")
        self.beam.proc = proc
        self.assertEqual(beam.process_identity(123, proc), "")
        with patch.object(beam.os, "kill") as kill:
            self.beam.stop_processes([dict(pid=123, identity="100")], retry="undo")
        kill.assert_not_called()

    def test_spawn_reaps_exited_child_without_waiting_for_the_setup_terminal(self):
        pid = beam.System().spawn([sys.executable, "-c", "pass"])
        deadline = time.monotonic() + 3
        while Path(f"/proc/{pid}").exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(Path(f"/proc/{pid}").exists())

    def test_admin_and_pin_share_private_browser_for_authentication(self):
        self.beam.status = lambda: dict(adminUp=True, adminUrl="https://localhost:47990")
        self.system.have = lambda name: name in ("omarchy-launch-browser", "omarchy-launch-webapp")
        with patch.object(self.system, "spawn", create=True) as spawn:
            self.assertTrue(self.beam.open_admin()["ok"])
            spawn.assert_called_with(["omarchy-launch-browser", "--private", "https://localhost:47990"])
            self.assertTrue(self.beam.open_admin(pin=True)["ok"])
            spawn.assert_called_with(["omarchy-launch-browser", "--private", "https://localhost:47990/pin"])

    def test_admin_uses_default_browser_fallback_and_reports_launch_failure(self):
        self.beam.status = lambda: dict(adminUp=True, adminUrl="https://localhost:47990")
        with patch.object(self.system, "spawn", create=True) as spawn:
            self.assertTrue(self.beam.open_admin()["ok"])
            spawn.assert_called_with(["xdg-open", "https://localhost:47990"])
            spawn.side_effect = OSError("browser unavailable")
            self.assertFalse(self.beam.open_admin()["ok"])

    def test_repair_migrates_running_sunshine_to_notification_browser(self):
        self.system.have = lambda name: name == "sunshine"
        self.beam.status = lambda: {"streaming": False}
        self.beam.units = lambda: []
        self.beam.firewall = lambda: {"firewallReady": True}
        old = [dict(pid=123, identity="1", browser=False)]
        current = [dict(pid=456, identity="2", browser=True)]
        with patch.object(self.beam.display, "install", return_value=False), \
                patch.object(self.beam.display.virtual, "install", return_value=False), \
                patch.object(self.beam, "stock_function"), \
                patch.object(self.beam, "stop_processes") as stop, \
                patch.object(self.beam, "processes", side_effect=[old, current, current]), \
                patch.object(self.system, "spawn", create=True) as spawn:
            self.beam.repair()
            stop.assert_called_once_with(old)
            self.assertEqual(spawn.call_args.args[0], [str(self.beam.browser.launcher)])
            self.assertTrue(self.beam.browser.ready())

    def test_repair_refuses_to_restart_an_active_stream(self):
        self.system.have = lambda name: name == "sunshine"
        self.beam.status = lambda: {"streaming": True}
        with patch.object(self.beam, "stop_processes") as stop:
            with self.assertRaises(beam.Failure):
                self.beam.repair()
            stop.assert_not_called()

    def test_install_avoids_broken_stock_service_enable_and_finishes_setup(self):
        installed = set()
        self.system.have = lambda name: name in installed
        def run(args, **kwargs):
            self.system.commands.append(args)
            if args[0] == "omarchy-pkg-add":
                installed.add(args[1])
            return 0, ""
        self.system.run = run
        with patch.object(self.beam, "progress"), patch.object(self.beam, "repair") as repair:
            self.assertTrue(self.beam.perform("install")["ok"])
            repair.assert_called_once()
        self.assertEqual(self.system.commands, [["omarchy-pkg-add", "qrencode"], ["omarchy-pkg-add", "sunshine"]])

    def test_failed_package_install_is_not_mistaken_for_service_mismatch(self):
        self.system.have = lambda name: False
        self.system.run = lambda args, **kwargs: (1 if args[-1] == "sunshine" else 0, "")
        with patch.object(self.beam, "progress"), patch.object(self.beam, "repair") as repair:
            with self.assertRaises(beam.Failure):
                self.beam.perform("install")
            repair.assert_not_called()

    def test_missing_package_after_success_is_reported_before_repair(self):
        self.system.have = lambda name: False
        with patch.object(self.beam, "progress"), patch.object(self.beam, "repair") as repair:
            with self.assertRaises(beam.Failure):
                self.beam.perform("install")
            repair.assert_not_called()


if __name__ == "__main__":
    unittest.main()
