"""Prints one JSON report per line for each FILE, using the Python binding.
Usage: python run_python.py <anchors.pem|-> <prevalence|-> FILE...   (run with the venv where isitai is installed)
"""
import json, os, sys

import isitai

anchors, prevalence, files = sys.argv[1], sys.argv[2], sys.argv[3:]
pem = None if anchors == "-" else open(anchors, encoding="utf-8").read()
prevalence = None if prevalence == "-" else float(prevalence)
for f in files:
    try:
        report = isitai.check_file(f, trust_anchors_pem=pem, prevalence=prevalence)
    except Exception as e:  # noqa: BLE001
        report = {"error": str(e)}
    print(json.dumps({"file": os.path.basename(f), "report": report}))
