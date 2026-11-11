"""Fails unless Cargo, npm and PyPI versions agree, and match the git tag if given.

Usage: python3 scripts/check_versions.py [vX.Y.Z[-alpha.N]]
The Cargo workspace version is the source of truth. npm uses the same semver string;
PyPI uses its PEP 440 form (0.1.0-alpha.0 -> 0.1.0a0).
"""
import json, re, sys, tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cargo = tomllib.loads((ROOT / "Cargo.toml").read_text())["workspace"]["package"]["version"]
npm = json.loads((ROOT / "bindings/node/package.json").read_text())["version"]
pypi = tomllib.loads((ROOT / "bindings/python/pyproject.toml").read_text())["project"]["version"]


def pep440(semver: str) -> str:
    m = re.fullmatch(r"(\d+\.\d+\.\d+)(?:-(alpha|beta|rc)\.(\d+))?", semver)
    if not m:
        sys.exit(f"unsupported version format: {semver}")
    base, pre, n = m.groups()
    return base + ({"alpha": "a", "beta": "b", "rc": "rc"}[pre] + n if pre else "")


errors = []
if npm != cargo:
    errors.append(f"bindings/node/package.json is {npm}, Cargo.toml is {cargo}")
if pypi != pep440(cargo):
    errors.append(f"bindings/python/pyproject.toml is {pypi}, expected {pep440(cargo)}")
if len(sys.argv) > 1 and sys.argv[1] != f"v{cargo}":
    errors.append(f"tag {sys.argv[1]} does not match v{cargo}")

if errors:
    sys.exit("version mismatch:\n  " + "\n  ".join(errors))
print(f"versions agree: cargo/npm {cargo}, pypi {pep440(cargo)}")
