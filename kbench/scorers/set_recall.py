"""
Scorer for code-retrieval tasks.

Parses the agent's fenced ```kbench answer block into a set of (name, file)
items, then compares to ground truth. Falls back to substring matching if no
fenced block is present.

ground_truth shape (DESIGN.md §8):
  {"method": "set", "expected": [["name","path"], ...]}
  (file may be "" / partial; matching is on the name primarily, file as a hint)
"""
from __future__ import annotations

import re

_FENCE_RE = re.compile(r"```kbench\s*\n(.*?)```", re.DOTALL)


def parse_answer(answer: str) -> set[str]:
    """Return the set of names the agent asserted (lowercased)."""
    names: set[str] = set()
    m = _FENCE_RE.search(answer or "")
    block = m.group(1) if m else (answer or "")
    for line in block.splitlines():
        line = line.strip().strip("`").strip()
        if not line or line.startswith("kbench"):
            continue
        name = line.split("|", 1)[0].strip()
        if name:
            names.add(name.lower())
    return names


def _gt_names(expected: list) -> set[str]:
    return {(e[0] if isinstance(e, list) else e).strip().lower() for e in expected}


def score(answer: str, ground_truth: dict) -> dict:
    """Return {recall, precision, f1, matched, predicted_n, expected_n}."""
    expected = _gt_names(ground_truth.get("expected", []))
    predicted = parse_answer(answer)

    if not predicted and not expected:
        return {"recall": 1.0, "precision": 1.0, "f1": 1.0,
                "matched": 0, "predicted_n": 0, "expected_n": 0}

    matched = predicted & expected
    recall = len(matched) / len(expected) if expected else 0.0
    precision = len(matched) / len(predicted) if predicted else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"recall": round(recall, 4), "precision": round(precision, 4),
            "f1": round(f1, 4), "matched": len(matched),
            "predicted_n": len(predicted), "expected_n": len(expected)}
