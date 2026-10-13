"""Exercise the notification launcher without opening a real browser."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "lib"))
from beam_browser import BrowserBridge, STOCK_AUTOSTART, admin_port, browser_command


class BrowserTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="beam browser ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.autostart = self.root / "autostart.lua"
        self.original = '-- custom startup\no.launch_on_start("music")\n' + STOCK_AUTOSTART + '\n'
        self.autostart.write_text(self.original)
        self.bridge = BrowserBridge(self.root / "state", self.autostart)

    def test_admin_aliases_and_custom_port_share_private_origin(self):
        for host in ("localhost", "127.0.0.1", "[::1]"):
            for path in ("", "/pin", "/config"):
                self.assertEqual(browser_command([f"https://{host}:48990{path}"], 48990, True),
                                 ["omarchy-launch-browser", "--private", f"https://localhost:48990{path}"])

    def test_unrelated_urls_and_missing_launcher_keep_default_opener(self):
        urls = ["https://example.com", "https://localhost.evil.test:47990/pin",
                "https://localhost:47990@evil.test/pin", "https://user@localhost:47990/pin",
                "http://localhost:47990/pin", "https://localhost:bad/pin",
                "https://localhost:47991/pin", "file:///tmp/example", "--help"]
        for url in urls:
            self.assertEqual(browser_command([url], 47990, True), ["/usr/bin/xdg-open", url])
        url = "https://localhost:47990/pin"
        self.assertEqual(browser_command([url], 47990, False), ["/usr/bin/xdg-open", url])

    def test_migration_preserves_other_startup_and_removal(self):
        self.assertTrue(self.bridge.install())
        self.assertTrue(self.bridge.ready())
        self.assertFalse(self.bridge.install())
        self.assertEqual((self.bridge.directory / "autostart.before.lua").read_text(), self.original)
        lines = self.autostart.read_text().splitlines()
        self.assertNotIn(STOCK_AUTOSTART, lines)
        self.assertIn('o.launch_on_start("music")', lines)
        # A path with spaces survives both the Lua string and shell layers.
        command = json.loads(self.bridge.line().split("(", 1)[1].split(") --", 1)[0])
        self.assertEqual(shlex.split(command), [str(self.bridge.launcher)])
        self.bridge.remove()
        self.assertEqual(self.autostart.read_text(), '-- custom startup\no.launch_on_start("music")\n')
        self.assertFalse(self.bridge.ready())

    def test_modified_helper_is_repaired_without_overwriting_backup(self):
        self.bridge.install()
        (self.bridge.directory / "xdg-open").write_text("broken")
        self.assertFalse(self.bridge.ready())
        self.assertTrue(self.bridge.install())
        self.assertTrue(self.bridge.ready())
        self.assertEqual((self.bridge.directory / "autostart.before.lua").read_text(), self.original)

    def test_repair_removes_reintroduced_duplicate_startup(self):
        self.bridge.install()
        with self.autostart.open("a") as stream:
            stream.write(STOCK_AUTOSTART + "\n" + self.bridge.line() + "\n")
        self.assertFalse(self.bridge.ready())
        self.assertTrue(self.bridge.install())
        self.assertEqual(self.autostart.read_text().splitlines().count(self.bridge.line()), 1)
        self.assertTrue(self.bridge.ready())

    def test_notification_process_uses_private_browser_and_restores_child_path(self):
        self.bridge.install()
        binaries = self.root / "bin"
        binaries.mkdir()
        sunshine = binaries / "sunshine"
        sunshine.write_text(f'#!{sys.executable}\nimport os, shutil, subprocess\n'
                            'assert os.environ["BEAM_SUNSHINE_BROWSER"] == "1"\n'
                            f'assert shutil.which("xdg-open") == {str(self.bridge.directory / "xdg-open")!r}\n'
                            'subprocess.run(["xdg-open", "https://localhost:47990/pin"], check=True)\n')
        browser = binaries / "omarchy-launch-browser"
        browser.write_text(f'#!{sys.executable}\nimport json, os, sys\n'
                           'print(json.dumps({"args": sys.argv[1:], "path": os.environ["PATH"], '
                           '"marker": os.getenv("BEAM_SUNSHINE_BROWSER")}))\n')
        sunshine.chmod(0o700)
        browser.chmod(0o700)
        path = str(binaries) + ":/usr/bin:/bin"
        env = dict(os.environ, PATH=path, XDG_CONFIG_HOME=str(self.root / "config"))
        result = json.loads(subprocess.check_output([self.bridge.launcher], env=env, text=True))
        self.assertEqual(result, dict(args=["--private", "https://localhost:47990/pin"], path=path, marker=None))

    def test_configured_port_and_invalid_port_fallback(self):
        config = self.root / "config/sunshine"
        config.mkdir(parents=True)
        with patch.dict(os.environ, XDG_CONFIG_HOME=str(config.parent)):
            self.assertEqual(admin_port(), 47990)
            for value, expected in (("48989", 48990), ("broken", 47990), ("65535", 47990)):
                (config / "sunshine.conf").write_text("port = " + value + "\n")
                self.assertEqual(admin_port(), expected)

    def test_native_launcher_prepares_before_sunshine_and_blocks_on_failure(self):
        self.bridge.install()
        binaries = self.root / "native-bin"
        binaries.mkdir()
        marker = self.root / "prepared"
        helper = binaries / "beam"
        helper.write_text(f'#!{sys.executable}\nfrom pathlib import Path\nimport sys\n'
                          'assert sys.argv[1:] == ["prepare-display"]\n'
                          f'Path({str(marker)!r}).touch()\n')
        sunshine = binaries / "sunshine"
        sunshine.write_text(f'#!{sys.executable}\nfrom pathlib import Path\nimport json,sys\n'
                            f'assert Path({str(marker)!r}).exists()\nprint(json.dumps(sys.argv[1:]))\n')
        helper.chmod(0o700)
        sunshine.chmod(0o700)
        (self.bridge.directory.parent / "display-virtual.json").write_text(json.dumps(dict(entry=str(helper), output="BEAM-IPAD")))
        env = dict(os.environ, PATH=str(binaries) + ":/usr/bin:/bin")
        actual = json.loads(subprocess.check_output([self.bridge.launcher], env=env, text=True))
        self.assertEqual(actual, ["output_name=BEAM-IPAD", "capture=wlr"])
        helper.write_text(f'#!{sys.executable}\nraise SystemExit(1)\n')
        result = subprocess.run([self.bridge.launcher], env=env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("could not prepare", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_launcher_record_rejects_reused_pid_or_old_start_time(self):
        self.bridge.install()
        record = self.bridge.directory / "process.json"
        record.write_text(json.dumps(dict(pid=123, identity="456", version=1)))
        self.assertTrue(self.bridge.owns_process(123, "456"))
        self.assertFalse(self.bridge.owns_process(123, "789"))
        self.assertFalse(self.bridge.owns_process(124, "456"))
        record.write_text("incomplete")
        self.assertFalse(self.bridge.owns_process(123, "456"))


if __name__ == "__main__":
    unittest.main()
