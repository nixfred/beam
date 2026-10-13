#!/usr/bin/env python3
"""Replay a historical model audit against its isolated, unchanged baseline."""
import argparse
import io
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("model", choices=("kimi3", "grok"))
args = parser.parse_args()
here = Path(__file__).resolve().parent
repo = here.parents[2]
with tempfile.TemporaryDirectory(prefix="beam-audit-replay-") as directory:
    root = Path(directory)
    archive = subprocess.check_output(["git", "archive", "99ee8b5"], cwd=repo)
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(root, filter="data")
    shutil.copytree(here / args.model / "audit_tests", root / "audit_tests",
                    ignore=shutil.ignore_patterns("__pycache__"))
    subprocess.run(["python", "-m", "unittest", "discover", "-s", "audit_tests", "-p", "test_*.py", "-v"],
                   cwd=root, check=True)
    for test in sorted((root / "audit_tests").glob("*.test.js")):
        subprocess.run(["node", str(test)], cwd=root, check=True)
