"""Reference detector: the score is the word count. It proves the pipeline end to end
and measures the length confound of each split (an AUROC far from 0.5 means that length
alone separates the classes there)."""
NAME = "length_baseline"
NEEDS_TRAINING = False
MODEL = "none"


def score(texts: list[str]) -> list[float]:
    return [float(len(t.split())) for t in texts]
