"""Shared harness for the kimi3 audit. Synthetic files and commands only."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_beam():
    spec = importlib.util.spec_from_file_location("beam", ROOT / "lib/beam.py")
    beam = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(beam)
    return beam

class FakeSystem:
    """Records commands; caller programs per-command responses."""
    def __init__(self, present=(), responses=None):
        self.present = set(present)
        self.responses = responses or {}
        self.commands = []

    def have(self, name):
        return name in self.present

    def run(self, args, **kwargs):
        self.commands.append(list(args))
        key = tuple(args)
        if key in self.responses:
            return self.responses[key]
        return 0, ""
