"""Firewall saved-rules and active-status branches disagree about tailscale; token parsing probes."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from audit_helpers import load_beam, FakeSystem

beam = load_beam()
MARKER_HEX = "omarchy-sunshine".encode().hex()


def saved_rules(ports, tailscale=False):
    lines = []
    for proto, numbers in ports.items():
        for p in numbers:
            for cidr in beam.PRIVATE_CIDRS:
                suffix = "in_tailscale0" if tailscale else "in"
                lines.append(f"### tuple ### allow {proto} {p} 0.0.0.0/0 any {cidr} {suffix} comment={MARKER_HEX}")
    return "\n".join(lines) + "\n"


class FirewallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.etc = self.home / "etc"
        (self.etc / "ufw").mkdir(parents=True)

    def make(self, ufw_output, tailscale=False):
        system = FakeSystem(present={"ufw"}, responses={("sudo", "-n", "ufw", "status"): (0, ufw_output)})
        b = beam.Beam(home=self.home, system=system, etc=self.etc)
        if tailscale:
            (self.home / "sys/class/net/tailscale0").mkdir(parents=True, exist_ok=True)
        return b

    def test_saved_branch_ignores_tailscale_requirement(self):
        (self.etc / "ufw/user.rules").write_text(saved_rules(beam.PORTS))
        b = self.make("permission denied", tailscale=True)
        state = b.firewall()
        # BUG: the saved-rules branch never checks per-port tailscale0 rules,
        # while the active branch (below) requires them. Same rule set flips
        # between ready and incomplete depending on which branch answered.
        self.assertEqual(state["firewallState"], "configured")
        self.assertTrue(state["firewallReady"])

    def test_active_branch_requires_tailscale_rules(self):
        entries = "".join(
            f"{p}/{proto} ALLOW IN {cidr} # omarchy-sunshine\n"
            for proto, ports in beam.PORTS.items() for p in ports for cidr in beam.PRIVATE_CIDRS)
        b = self.make("Status: active\n" + entries, tailscale=True)
        self.assertEqual(b.firewall()["firewallState"], "incomplete")
        b2 = self.make("Status: active\n" + entries +
                       "".join(f"{p}/{proto} ALLOW IN Anywhere on tailscale0 # omarchy-sunshine\n"
                               for proto, ports in beam.PORTS.items() for p in ports),
                       tailscale=True)
        self.assertEqual(b2.firewall()["firewallState"], "open")

    def test_deny_rules_and_near_miss_tokens_do_not_count(self):
        lines = []
        for proto, ports in beam.PORTS.items():
            for p in ports:
                for cidr in beam.PRIVATE_CIDRS:
                    lines.append(f"{p}/{proto} DENY IN {cidr} # omarchy-sunshine")
        b = self.make("Status: active\n" + "\n".join(lines) + "\n")
        self.assertEqual(b.firewall()["firewallState"], "incomplete")
        # A different port whose token merely resembles a real one must not satisfy it.
        near = "".join(f"1{p}/{proto} ALLOW IN {cidr} # omarchy-sunshine\n"
                       for proto, ports in beam.PORTS.items() for p in ports for cidr in beam.PRIVATE_CIDRS)
        b2 = self.make("Status: active\n" + near)
        self.assertEqual(b2.firewall()["firewallState"], "incomplete")

    def test_unknown_when_neither_sudo_nor_saved_rules_are_readable(self):
        b = self.make("sudo: a password is required\n")
        state = b.firewall()
        self.assertEqual(state["firewallState"], "unknown")
        self.assertFalse(state["firewallKnown"])
        self.assertFalse(state["firewallReady"])


if __name__ == "__main__":
    unittest.main()
