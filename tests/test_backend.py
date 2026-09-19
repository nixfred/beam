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


if __name__ == "__main__":
    unittest.main()
