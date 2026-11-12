"""Run the isitai CLI on a labelled corpus and compare with its `expected.json`.

Usage: python3 -I check_expected.py <isitai binary> <corpus dir> [--anchors roots.pem]
                                    [--timeout 60] [--slow 10] [--out results.json] [--only-bad]

`expected.json` maps a file name to either a verdict string (format of make_signed.py) or an
object {verdict, generator?, media?, category?, human?, note?} (format of make_synthetic.py).

One process per file, with a timeout. Exit code 1 on any mismatch, crash, hang or exit-code
inconsistency; 0 when everything matches. Standard library only.

Columns: status, file, expected, got, exit code, wall time, peak RSS, evidence ids.
Status: ok | VERDICT | GENERATOR | MEDIA | EXIT (exit code does not fit the verdict) |
        CRASH (panic, signal, no JSON) | SLOW (right answer, but slower than --slow seconds) |
        TIMEOUT (killed after --timeout seconds).
"""
import json
import os
import re
import signal
import subprocess
import sys
import time

args = sys.argv[1:]


def opt(name, default=None, flag=False):
    if name not in args:
        return default
    i = args.index(name)
    args.pop(i)
    return True if flag else args.pop(i)


anchors = opt("--anchors")
timeout = float(opt("--timeout", "60"))
slow = float(opt("--slow", "10"))
out_path = opt("--out")
only_bad = opt("--only-bad", False, flag=True)
binary, corpus = args
TIME = "/usr/bin/time"
time_flag = ["-l"] if sys.platform == "darwin" else ["-v"]
has_time = os.path.exists(TIME)

with open(os.path.join(corpus, "expected.json"), encoding="utf-8") as f:
    expected = json.load(f)

AI_VERDICTS = ("ai-proven", "ai-signal", "inconsistent")
rows, bad = [], 0
for name in sorted(expected):
    exp = expected[name]
    if isinstance(exp, str):
        exp = {"verdict": exp}
    path = os.path.join(corpus, name)
    cmd = ([TIME] + time_flag if has_time else []) + [binary] + (["--anchors", anchors] if anchors else []) + [path]
    row = {"file": name, "expected": exp["verdict"], "category": exp.get("category", "-"), "human": exp.get("human"),
           "size": os.path.getsize(path) if os.path.exists(path) else -1}
    t0 = time.perf_counter()
    # Own process group: on timeout the CLI is killed too, not only /usr/bin/time.
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        p = subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
        row["seconds"] = time.perf_counter() - t0
        err = p.stderr.decode("utf-8", "replace")
        m = re.search(r"(\d+)\s+maximum resident set size", err) or re.search(r"Maximum resident set size \(kbytes\): (\d+)", err)
        if m:
            row["rss_mb"] = int(m.group(1)) / (1e6 if sys.platform == "darwin" else 1e3)
        row["exit"] = p.returncode
        row["stdout_bytes"] = len(p.stdout)
        try:
            r = json.loads(p.stdout)[0]
        except Exception:
            r = None
        if r is None:
            row["status"] = "CRASH"
            row["got"] = (err.strip().splitlines() or ["no output"])[0][:60]
        else:
            row["got"] = r["verdict"]
            row["generator"] = r.get("generator")
            row["media"] = r.get("media")
            row["warnings"] = r.get("warnings", [])
            ev = r.get("evidence", [])
            row["evidence"] = sorted({f'{e["id"]}:{e["strength"]}' for e in ev})
            row["evidence_count"] = len(ev)
            want_exit = 0 if r["verdict"] in ("no-signal", "capture-proven") else 1
            if r["verdict"] != exp["verdict"]:
                row["status"] = "VERDICT"
            elif "generator" in exp and exp["generator"] != r.get("generator"):
                row["status"] = "GENERATOR"
            elif "media" in exp and exp["media"] != r.get("media"):
                row["status"] = "MEDIA"
            elif p.returncode != want_exit:
                row["status"] = "EXIT"
            elif row["seconds"] > slow:
                row["status"] = "SLOW"
            else:
                row["status"] = "ok"
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        row.update(status="TIMEOUT", got=f">{timeout:.0f}s", seconds=timeout, exit=None)
    if row["status"] != "ok":
        bad += 1
    rows.append(row)

w = max(len(r["file"]) for r in rows)
print(f'{"status":<9} {"file":<{w}} {"expected":<14} {"got":<14} {"exit":>4} {"sec":>6} {"MB":>5}  evidence')
for r in rows:
    if only_bad and r["status"] == "ok":
        continue
    got = r["got"]
    if r["status"] == "GENERATOR":
        got += f' gen={r.get("generator")}'
    if r["status"] == "MEDIA":
        got += f' media={r.get("media")}'
    ev = ",".join(r.get("evidence", []))[:70]
    print(f'{r["status"]:<9} {r["file"]:<{w}} {r["expected"]:<14} {got:<14} {str(r.get("exit")):>4} '
          f'{r.get("seconds", 0):6.2f} {r.get("rss_mb", 0):5.0f}  {ev}')

# Summary per category.
cats = {}
for r in rows:
    c = cats.setdefault(r["category"], [0, 0])
    c[0] += 1
    c[1] += r["status"] != "ok"
print("\nper category (files / not ok): " + ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in sorted(cats.items())))

# Criterion 1 of the spec: no false ai-proven, no false strong ai-signal on human content.
human = [r for r in rows if r["human"]]
if human:
    def strongest(r):
        ev = r.get("evidence", [])
        return "proof" if any(e.endswith(":proof") for e in ev) else "strong" if any(e.endswith(":strong") for e in ev) else "weak"

    fp = [r for r in human if r.get("got") in AI_VERDICTS]
    proven = [r["file"] for r in fp if r["got"] == "ai-proven"]
    strong = [r["file"] for r in fp if r["got"] != "ai-proven" and strongest(r) in ("strong", "proof")]
    weak2 = [r["file"] for r in fp if r["got"] != "ai-proven" and strongest(r) == "weak"]
    print(f"\ncriterion 1 on {len(human)} human files:")
    print(f"  false ai-proven: {len(proven)} {proven}")
    print(f"  false AI verdict with strong evidence: {len(strong)} {strong}")
    print(f"  false AI verdict from two weak rules only: {len(weak2)} {weak2}")

slow = sorted(rows, key=lambda r: -r.get("seconds", 0))[:3]
fat = sorted(rows, key=lambda r: -r.get("rss_mb", 0))[:3]
print("\nslowest: " + ", ".join(f'{r["file"]} {r.get("seconds", 0):.2f}s' for r in slow))
print("largest peak RSS: " + ", ".join(f'{r["file"]} {r.get("rss_mb", 0):.0f}MB' for r in fat))
print(f"\n{len(rows)} files, {bad} not ok" + (f", anchors={anchors}" if anchors else ""))

if out_path:
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)
sys.exit(1 if bad else 0)
