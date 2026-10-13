"""Exercise real Qt Process exit ordering with an isolated, harmless helper."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("qs"), "Quickshell is not installed")
class ServiceRuntimeTests(unittest.TestCase):
    def run_timeout(self, ignore_term):
        with tempfile.TemporaryDirectory(prefix="beam-service-test-") as directory:
            root = Path(directory)
            source = Path(__file__).parents[1]
            # Only shorten the test deadlines. The process/state code is real.
            qml = (source / "Service.qml").read_text().replace("interval: 15000", "interval: 500")
            (root / "Service.qml").write_text(qml)
            shutil.copyfile(source / "ServiceState.js", root / "ServiceState.js")
            (root / "bin").mkdir()
            helper = root / "bin/omarchy-beam"
            helper.write_text('''#!/usr/bin/env python3
import json, signal, sys, time
from pathlib import Path
action = sys.argv[1]
if action == 'status':
    print(json.dumps(dict(installed=False, running=False, streaming=False,
        ready=False, processes=0, nextStep=2, actionBusy=False, lastAction={})))
elif action == 'slow':
    def terminate(*_):
        time.sleep(.2)
        print(json.dumps(dict(ok=True, action=action, message='late old result')), flush=True)
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, signal.SIG_IGN if IGNORE_TERM else terminate)
    time.sleep(10)
else:
    Path(__file__).resolve().parent.parent.joinpath('fast-ran').touch()
    print(json.dumps(dict(ok=True, action=action, message='next action succeeded')))
'''.replace("IGNORE_TERM", repr(ignore_term)))
            helper.chmod(0o700)
            (root / "shell.qml").write_text('''import QtQuick
import Quickshell
ShellRoot {
    Service { id: service }
    Timer { interval: 100; running: true; onTriggered: {
        service.run(["slow"]); service.run(["fast"]);
    } }
    Timer { interval: 3500; running: true; onTriggered: {
        console.log("BEAM_RESULT", JSON.stringify({report: service.actionReport,
            busy: service.busy, pending: service.pending})); Qt.quit();
    } }
}
''')
            env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="",
                       QT_STYLE_OVERRIDE="Fusion", XDG_RUNTIME_DIR=directory,
                       XDG_CACHE_HOME=str(root / "cache"))
            env.pop("WAYLAND_DISPLAY", None)
            env.pop("DISPLAY", None)
            env.pop("DBUS_SESSION_BUS_ADDRESS", None)
            done = subprocess.run(["qs", "-p", str(root / "shell.qml")], env=env,
                                  capture_output=True, text=True, timeout=8)
            output = done.stdout + done.stderr
            self.assertEqual(done.returncode, 0, output)
            match = re.search(r"BEAM_RESULT (\{[^\n]+\})", output)
            self.assertIsNotNone(match, output)
            state = json.loads(match[1])
            self.assertTrue((root / "fast-ran").exists(), output)
            self.assertEqual(state["report"]["state"], "success", output)
            self.assertEqual(state["report"]["message"], "next action succeeded", output)
            self.assertEqual(state["pending"], [], output)
            self.assertFalse(state["busy"], output)

    def test_late_exit_cannot_overwrite_next_action_result(self):
        self.run_timeout(ignore_term=False)

    def test_unresponsive_helper_is_killed_before_next_action(self):
        self.run_timeout(ignore_term=True)
