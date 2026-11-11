"""Criterion 5: the CLI, the Node binding and the Python binding must return the
same report for the same file. Runs all three on every file of the given dirs,
with and without trust anchors, and diffs the reports (CLI `path` field removed).

Usage: python3 -I diff.py <isitai CLI> <bindings/node dir> <python with isitai installed> <anchors.pem> DIR...
Exit code 0 when every report is identical.
"""
import json, os, subprocess, sys

cli, node_dir, py, anchors, *dirs = sys.argv[1:]
here = os.path.dirname(os.path.abspath(__file__))
files = sorted(
    os.path.join(d, n) for d in dirs for n in os.listdir(d)
    if os.path.isfile(os.path.join(d, n)) and not n.endswith((".pem", ".json"))
)


def lines(cmd):
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return {o["file"]: o["report"] for o in map(json.loads, out.splitlines())}


def cli_reports(use_anchors):
    reports = {}
    for f in files:
        cmd = [cli] + (["--anchors", anchors] if use_anchors else []) + [f]
        p = subprocess.run(cmd, capture_output=True, text=True)
        r = json.loads(p.stdout)[0] if p.stdout.strip() else {"error": p.stderr.strip()}
        r.pop("path", None)
        reports[os.path.basename(f)] = r
    return reports


def canon(r):
    return json.dumps(r, sort_keys=True, ensure_ascii=False)


failures = 0
for use_anchors in (False, True):
    a = anchors if use_anchors else "-"
    results = {
        "cli": cli_reports(use_anchors),
        "node": lines(["node", os.path.join(here, "run_node.js"), node_dir, a, *files]),
        "python": lines([py, "-I", os.path.join(here, "run_python.py"), a, *files]),
    }
    for f in files:
        name = os.path.basename(f)
        variants = {k: canon(v.get(name)) for k, v in results.items()}
        if len(set(variants.values())) != 1:
            failures += 1
            print(f"DIFF {name} anchors={use_anchors}")
            for k, v in variants.items():
                print(f"  {k}: {v[:300]}")
    print(f"anchors={use_anchors}: {len(files)} files compared")

print("identical" if failures == 0 else f"{failures} differences")
sys.exit(1 if failures else 0)
