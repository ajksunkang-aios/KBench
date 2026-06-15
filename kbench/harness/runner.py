"""
KBench runner — orchestrates task × arm × replicate, writes result records.

Each result matches DESIGN.md §8: run_id, task_id, vertical, arm, model,
replicate, accuracy{recall,precision,f1}, cost{tokens_in,out,cache, tool_calls,
wall_seconds}. Results land under results/<run_id>/retrieval/<id>.json.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from .agent import make_client, run_agent
from .arms import build_arm
from ..scorers import set_recall

SCORERS = {"set_recall_precision": set_recall.score}


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run(tasks: list[dict], arms: list[str], reps: int, model: str,
        repo_root: Path, kgraph_repo: Path | None, db_path: Path | None,
        results_dir: Path, max_turns: int = 12) -> str:
    """Run the matrix; return the run_id."""
    run_id = f"{_now_iso()}"
    out_root = results_dir / run_id / "retrieval"
    out_root.mkdir(parents=True, exist_ok=True)

    # Build per-arm (definitions, dispatch) once; arms are stateless across tasks.
    arm_tools = {}
    for arm in arms:
        arm_tools[arm] = build_arm(arm, repo_root, kgraph_repo, db_path)

    client = make_client()

    total = len(tasks) * len(arms) * reps
    done = 0
    for task in tasks:
        tid = task["id"]
        scorer = SCORERS.get(task.get("scorer", "set_recall_precision"), set_recall.score)
        for arm in arms:
            tools, dispatch = arm_tools[arm]
            for rep in range(1, reps + 1):
                done += 1
                print(f"[{done}/{total}] {tid} | {arm} | rep {rep} …", flush=True)
                try:
                    m = run_agent(client, model, task["prompt"], tools, dispatch,
                                  max_turns=max_turns)
                    acc = scorer(m["answer"], task.get("ground_truth", {}))
                    result = {
                        "run_id": run_id, "task_id": tid,
                        "vertical": task.get("vertical", "retrieval"),
                        "subtype": task.get("subtype", ""),
                        "tier": task.get("tier", ""),
                        "arm": arm, "model": model, "replicate": rep,
                        "accuracy": {k: acc[k] for k in ("recall", "precision", "f1")},
                        "cost": {
                            "tokens_in": m["tokens_in"],
                            "tokens_out": m["tokens_out"],
                            "tokens_cache": m["tokens_cache"],
                            "tool_calls": m["tool_calls"],
                            "wall_seconds": m["wall_seconds"],
                        },
                        "turns": m["turns"],
                        "answer": m["answer"],
                    }
                    status = f"acc={acc['f1']:.2f} tok={m['tokens_in']+m['tokens_out']} calls={sum(m['tool_calls'].values())} {m['wall_seconds']}s"
                except Exception as e:
                    result = {"run_id": run_id, "task_id": tid, "arm": arm,
                              "model": model, "replicate": rep,
                              "error": f"{type(e).__name__}: {e}"}
                    status = f"ERROR: {e}"
                print(f"        → {status}", flush=True)
                (out_root / f"{tid.replace('/', '_')}__{arm}__{rep}.json").write_text(
                    json.dumps(result, indent=2))

    return run_id
