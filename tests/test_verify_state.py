#!/usr/bin/env python3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "scripts" / "verify-state"


def check(*args, code=0, text=None):
    result = subprocess.run([str(VERIFY), *args], text=True, capture_output=True)
    assert result.returncode == code, result.stdout + result.stderr
    if text:
        assert text in result.stdout, result.stdout


check("--fixture", str(ROOT / "tests/fixtures/behavior-changing-model-drift.yaml"), code=1, text="model drift")
check("--fixture", str(ROOT / "tests/fixtures/dormant-extra.yaml"), text="WARN: dormant")
check("--fixture", str(ROOT / "tests/fixtures/active-extra.yaml"), code=1, text="behavior-changing unexpected profile")
print("ok")
