"""Prints one JSON report per line for each FILE, using the Python binding.
Usage: python run_python.py <anchors.pem|-> FILE...   (run with the venv where isitai is installed)
"""
import json, os, sys

import isitai

anchors, files = sys.argv[1], sys.argv[2:]
pem = None if anchors == "-" else open(anchors, encoding="utf-8").read()
for f in files:
    try:
        report = isitai.check_file(f, trust_anchors_pem=pem)
    except Exception as e:  # noqa: BLE001
        report = {"error": str(e)}
    print(json.dumps({"file": os.path.basename(f), "report": report}))
