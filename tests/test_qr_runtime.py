"""Verify QR cache recovery with the real generator and Qt image loader."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(shutil.which("qs") and shutil.which("qrencode"), "Quickshell and qrencode are required")
class QrRuntimeTests(unittest.TestCase):
    def test_poisoned_cache_loads_and_can_be_retried_in_qt(self):
        with tempfile.TemporaryDirectory(prefix="beam-qr-test-") as directory:
            root = Path(directory)
            source = Path(__file__).parents[1]
            shutil.copytree(source / "bin", root / "bin")
            shutil.copytree(source / "lib", root / "lib", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copyfile(source / "QrCode.qml", root / "QrCode.qml")
            content = "192.0.2.20"
            cached = root / "cache/omarchy/beam" / ("qr-" + hashlib.sha256(content.encode()).hexdigest() + ".png")
            cached.parent.mkdir(parents=True)
            cached.write_bytes(b"invalid cached image")
            (root / "shell.qml").write_text('''import QtQuick
import Quickshell
ShellRoot {
    QrCode { id: qr; text: "192.0.2.20"; cli: Qt.resolvedUrl("bin/omarchy-beam").toString().slice(7) }
    property bool firstLoaded: false
    Timer { interval: 1200; running: true; onTriggered: {
        firstLoaded = qr.loaded; qr.retry();
    } }
    Timer { interval: 2400; running: true; onTriggered: {
        console.log("BEAM_QR", JSON.stringify({first: firstLoaded, loaded: qr.loaded, error: qr.error})); Qt.quit();
    } }
}
''')
            env = dict(os.environ, HOME=directory, QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="",
                       QT_STYLE_OVERRIDE="Fusion", XDG_RUNTIME_DIR=directory,
                       XDG_CONFIG_HOME=str(root / "config"), XDG_STATE_HOME=str(root / "state"),
                       XDG_CACHE_HOME=str(root / "cache"))
            for key in ("WAYLAND_DISPLAY", "DISPLAY", "DBUS_SESSION_BUS_ADDRESS"):
                env.pop(key, None)
            done = subprocess.run(["qs", "-p", str(root / "shell.qml")], env=env,
                                  capture_output=True, text=True, timeout=8)
            output = done.stdout + done.stderr
            self.assertEqual(done.returncode, 0, output)
            match = re.search(r"BEAM_QR (\{[^\n]+\})", output)
            self.assertIsNotNone(match, output)
            self.assertEqual(json.loads(match[1]), dict(first=True, loaded=True, error=""), output)
