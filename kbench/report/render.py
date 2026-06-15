"""
KBench report renderer — aggregates a run's results into markdown + JSON.

Produces an A-vs-B comparison (accuracy + cost), broken down by tier
(direct-retrieval = cost gap; compiler-aware = accuracy gap), per DESIGN.md §7.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def _load(results_root: Path, run_id: str) -> list[dict]:
    d = results_root / run_id / "retrieval"
    if not d.is_dir():
        return []
    rows = []
    for f in sorted(d.glob("*.json")):
        try:
            rows.append(json.loads(f.read_text()))
        except Exception:
            pass
    return rows


def _agg(records: list[dict]) -> dict:
    ok = [r for r in records if "accuracy" in r]
    if not ok:
        return {"n": 0}
    f1 = [r["accuracy"]["f1"] for r in ok]
    tok = [r["cost"]["tokens_in"] + r["cost"]["tokens_out"] for r in ok]
    calls = [sum(r["cost"]["tool_calls"].values()) for r in ok]
    wall = [r["cost"]["wall_seconds"] for r in ok]
    n = len(ok)
    return {
        "n": n,
        "avg_f1": round(sum(f1) / n, 3),
        "avg_tokens": round(sum(tok) / n),
        "avg_calls": round(sum(calls) / n, 1),
        "avg_wall": round(sum(wall) / n, 2),
    }


def render(run_id: str, results_dir: Path, reports_dir: Path) -> tuple[Path, Path]:
    rows = _load(results_dir, run_id)
    reports_dir.mkdir(parents=True, exist_ok=True)

    by_arm = defaultdict(list)
    by_arm_tier = defaultdict(lambda: defaultdict(list))
    per_task = defaultdict(dict)
    for r in rows:
        if "error" in r:
            continue
        arm = r["arm"]
        by_arm[arm].append(r)
        tier = r.get("tier") or "untiered"
        by_arm_tier[arm][tier].append(r)
        per_task[r["task_id"]][arm] = r

    summary = {arm: _agg(recs) for arm, recs in by_arm.items()}
    tiers = {arm: {t: _agg(recs) for t, recs in d.items()}
             for arm, d in by_arm_tier.items()}

    # ── markdown ──
    md = [f"# KBench Report — {run_id}", "",
          f"Model: `{rows[0]['model']}`" if rows else "", "",
          "## Summary (arm comparison)", "",
          "| Arm | N | avg F1 | avg tokens | avg tool-calls | avg time (s) |",
          "|---|---:|---:|---:|---:|---:|"]
    for arm in sorted(summary):
        s = summary[arm]
        md.append(f"| {arm} | {s['n']} | {s.get('avg_f1','—')} | "
                  f"{s.get('avg_tokens','—')} | {s.get('avg_calls','—')} | "
                  f"{s.get('avg_wall','—')} |")

    md += ["", "## By tier", "",
           "> direct-retrieval → cost gap (grep can solve). "
           "compiler-aware → accuracy gap (grep misses indirect).", ""]
    for tier in sorted({t for d in tiers.values() for t in d}):
        md.append(f"### {tier}")
        md.append("| Arm | N | avg F1 | avg tokens | avg calls | avg time |")
        md.append("|---|---:|---:|---:|---:|---:|")
        for arm in sorted(tiers):
            if tier in tiers[arm]:
                s = tiers[arm][tier]
                md.append(f"| {arm} | {s['n']} | {s.get('avg_f1','—')} | "
                          f"{s.get('avg_tokens','—')} | {s.get('avg_calls','—')} | "
                          f"{s.get('avg_wall','—')} |")
        md.append("")

    md += ["## Per task × arm", "",
           "| task | arm | F1 | tokens | calls | time | tool usage |",
           "|---|---|---:|---:|---:|---:|---|"]
    for tid in sorted(per_task):
        for arm in sorted(per_task[tid]):
            r = per_task[tid][tid] if False else per_task[tid][arm]
            if "accuracy" not in r:
                continue
            usage = ", ".join(f"{k}:{v}" for k, v in sorted(
                r["cost"]["tool_calls"].items())) or "—"
            md.append(f"| {tid} | {arm} | {r['accuracy']['f1']} | "
                      f"{r['cost']['tokens_in']+r['cost']['tokens_out']} | "
                      f"{sum(r['cost']['tool_calls'].values())} | "
                      f"{r['cost']['wall_seconds']} | {usage} |")

    md_path = reports_dir / f"{run_id}.md"
    md_path.write_text("\n".join(md))
    json_path = reports_dir / f"{run_id}.json"
    json_path.write_text(json.dumps({"run_id": run_id, "summary": summary,
                                     "tiers": tiers, "per_task": {
                                         tid: {arm: {"f1": r.get("accuracy", {}).get("f1"),
                                                     "tokens": (r["cost"]["tokens_in"]+r["cost"]["tokens_out"]) if "cost" in r else None,
                                                     "calls": sum(r["cost"]["tool_calls"].values()) if "cost" in r else None,
                                                     "wall": r.get("cost", {}).get("wall_seconds")}
                                              for arm, r in d.items() if "accuracy" in r}
                                         for tid, d in per_task.items()}}, indent=2))
    return md_path, json_path
