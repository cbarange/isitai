"""The library as it is today: the deterministic text layer of isitai (regex rules for
copy-paste artefacts, crates/isitai-core/rules/text.toml), through the Python binding.

Score: 1.0 when the report holds at least one strong text evidence (verdict ai-signal),
0.5 when it holds weak evidence only, 0.0 when it holds none.
"""
import isitai

NAME = "isitai_rules"
NEEDS_TRAINING = False
MODEL = "none (regex rules compiled into the isitai wheel, 4.6 MB)"


def score_one(text: str) -> float:
    report = isitai.check_text(text)
    evidence = [e for e in report.get("evidence", []) if e.get("origin", "ai") == "ai"]
    if any(e.get("strength") == "strong" for e in evidence):
        return 1.0
    if evidence:
        return 0.5
    return 0.0


def score(texts: list[str]) -> list[float]:
    return [score_one(t) for t in texts]
