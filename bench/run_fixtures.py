"""Run the isitai CLI on every fixture, with and without test trust anchors.
Prints verdict, evidence, warnings, wall time and peak RSS per file.
Usage: python3 -I run_fixtures.py <isitai-binary> <fixtures-dir> <anchors.pem>
"""
import json, os, re, subprocess, sys

binary, fixtures, anchors = sys.argv[1:4]
rows = []
for name in sorted(os.listdir(fixtures)):
    path = os.path.join(fixtures, name)
    if name.endswith(".pem") or not os.path.isfile(path):
        continue
    for use_anchors in (False, True):
        cmd = ["/usr/bin/time", "-l", binary] + (["--anchors", anchors] if use_anchors else []) + [path]
        p = subprocess.run(cmd, capture_output=True, text=True)
        rss = re.search(r"(\d+)\s+maximum resident set size", p.stderr)
        real = re.search(r"([\d.]+) real", p.stderr)
        try:
            r = json.loads(p.stdout)[0]
            ev = ",".join(f'{e["id"]}:{e["strength"]}' for e in r["evidence"])
            warn = (r.get("warnings") or [""])[0]
            line = f'{name:<34} {"A" if use_anchors else "-"} {r["media"]:<20} {r["verdict"]:<15} {ev[:60]:<60} | {warn[:70]}'
        except Exception:
            line = f"{name:<34} {'A' if use_anchors else '-'} ERROR exit={p.returncode} {p.stderr.strip().splitlines()[0][:100] if p.stderr else ''}"
        mb = int(rss.group(1)) / 1e6 if rss else -1
        print(f"{line} | {float(real.group(1)) if real else -1:.2f}s {mb:.0f}MB {os.path.getsize(path)/1e6:.1f}MBfile")
