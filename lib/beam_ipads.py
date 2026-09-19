"""Offline iPad screen catalog, sourced from Apple's technical specifications."""
import json
from pathlib import Path


CATALOG = json.loads(Path(__file__).with_name("ipads.json").read_text())
PROFILES = CATALOG["profiles"]


def profiles():
    """Only presentation facts go over the frequently polled status interface."""
    return [{k: p[k] for k in ("id", "family", "label", "width", "height")} for p in PROFILES]


def profile(identifier):
    return next((p for p in PROFILES if p["id"] == identifier), None)
