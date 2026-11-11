"""Time c2pa-python Reader per file, network off. Same protocol as examples/bench_files.rs.
Usage: python bench_c2pa_python.py <iterations> FILE...
"""
import json, os, sys, time

t0 = time.perf_counter()
import c2pa  # noqa: E402

import_ms = (time.perf_counter() - t0) * 1e3
print(f"import_ms={import_ms:.1f} version={c2pa.sdk_version()}", file=sys.stderr)

SETTINGS = {"verify": {"remote_manifest_fetch": False, "ocsp_fetch": False, "verify_trust": True}}
MIME = {".jpg": "image/jpeg", ".png": "image/png", ".mp4": "video/mp4", ".mp3": "audio/mpeg",
        ".heic": "image/heic", ".webp": "image/webp", ".pdf": "application/pdf", ".wav": "audio/wav"}

iterations = int(sys.argv[1])
for path in sys.argv[2:]:
    mime = MIME[os.path.splitext(path)[1].lower()]
    times, state = [], ""
    for _ in range(iterations):
        t = time.perf_counter()
        try:
            ctx = c2pa.Context.from_dict(SETTINGS)
            with open(path, "rb") as f, c2pa.Reader(mime, f, context=ctx) as r:
                state = json.loads(r.json()).get("validation_state", "?")
        except Exception as e:  # no manifest, unsupported...
            state = type(e).__name__
        times.append((time.perf_counter() - t) * 1e3)
    first = times[0]
    times.sort()
    print(json.dumps({"file": os.path.basename(path), "first_ms": first, "median_ms": times[len(times) // 2],
                      "p95_ms": times[min(int(len(times) * 0.95), len(times) - 1)], "state": state}))
