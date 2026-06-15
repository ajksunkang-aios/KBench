#!/usr/bin/env python3
"""
KBench CLI — run the code-retrieval benchmark and render a report.

Examples:
    # quick: 2 tasks × 2 arms × 1 rep (~4 agent calls) — verify the loop
    python -m kbench.cli run --quick \
        --repo /path/to/linux --kgraph-repo /path/to/KGraph \
        --db /path/to/linux/.kgraph/kgraph.db

    # full: all tasks × 2 arms × 3 reps
    python -m kbench.cli run --reps 3 ...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make the KBench package importable when run as a script from the repo root.
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from kbench.harness import runner  # noqa: E402
from kbench.report import render  # noqa: E402

TASKS_DIR = _REPO / "tasks" / "retrieval"
MANIFEST = _REPO / "tasks" / "retrieval" / "manifest.json"
RESULTS_DIR = _REPO / "results"
REPORTS_DIR = _REPO / "reports"

# Tasks used in --quick mode (one direct + one compiler-aware).
QUICK_IDS = {"retrieval/symbol_def/vfs_read", "retrieval/ops_impls/read_iter"}


def load_tasks() -> list[dict]:
    tasks = []
    for f in sorted(TASKS_DIR.glob("**/*.json")):
        if f.name == "manifest.json":
            continue
        try:
            tasks.append(json.loads(f.read_text()))
        except Exception as e:
            print(f"warn: skip {f}: {e}", file=sys.stderr)
    return tasks


def _preflight(repo: Path, db: Path | None, needs_db: bool) -> bool:
    """Verify the tree is at the pinned commit and (if needed) the db exists.

    Returns True if OK; prints guidance and returns False otherwise.
    """
    if not MANIFEST.exists():
        return True  # no pin declared → nothing to check
    manifest = json.loads(MANIFEST.read_text())
    commit = manifest.get("commit")
    if not commit:
        return True
    import subprocess
    try:
        head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
    except Exception:
        head = ""
    if head != commit:
        print(f"ERROR: tree HEAD ({head[:12]}) != pinned retrieval commit "
              f"({commit[:12]}, {manifest.get('describe','')}).\n"
              f"       Run: scripts/setup_retrieval.sh <linux> <kgraph-repo>",
              file=sys.stderr)
        return False
    if needs_db and (not db or not Path(db).exists()):
        print(f"ERROR: kgraph.db not found at {db}.\n"
              f"       Build it at the pinned commit: scripts/setup_retrieval.sh "
              f"<linux> <kgraph-repo>\n"
              f"       (scip-clang is Linux-only; build on Linux).",
              file=sys.stderr)
        return False
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="kbench", description="KBench code-retrieval benchmark")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the benchmark")
    r.add_argument("--repo", required=True, help="kernel source root")
    r.add_argument("--kgraph-repo", default=os.environ.get("KGRAPH_REPO"),
                   help="KGraph repo root (for the B-kgraph arm)")
    r.add_argument("--db", default=os.environ.get("KGRAPH_DB"),
                   help="kgraph.db path (for the B-kgraph arm)")
    r.add_argument("--arms", default="A-baseline,B-kgraph",
                   help="comma-separated arms (default both)")
    r.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", "glm-5"),
                   help="agent model id (default $ANTHROPIC_MODEL or glm-5)")
    r.add_argument("--reps", type=int, default=1, help="replicates per task×arm")
    r.add_argument("--quick", action="store_true",
                   help="2 tasks × selected arms × 1 rep (verify the loop)")
    r.add_argument("--max-turns", type=int, default=12)
    r.add_argument("--no-preflight", action="store_true",
                   help="skip the pinned-commit / db-exists check")
    args = ap.parse_args(argv)

    if args.cmd != "run":
        ap.print_help()
        return 1

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    if "B-kgraph" in arms and (not args.kgraph_repo or not args.db):
        print("ERROR: B-kgraph arm requires --kgraph-repo and --db", file=sys.stderr)
        return 2

    if not args.no_preflight:
        if not _preflight(Path(args.repo),
                          Path(args.db) if args.db else None,
                          needs_db=("B-kgraph" in arms)):
            return 2

    tasks = load_tasks()
    if args.quick:
        tasks = [t for t in tasks if t["id"] in QUICK_IDS] or tasks[:2]
        args.reps = 1
    if not tasks:
        print("ERROR: no tasks found under tasks/retrieval/", file=sys.stderr)
        return 2

    print(f"KBench run: {len(tasks)} tasks × {len(arms)} arms × {args.reps} reps "
          f"(model={args.model})")
    run_id = runner.run(
        tasks=tasks, arms=arms, reps=args.reps, model=args.model,
        repo_root=Path(args.repo),
        kgraph_repo=Path(args.kgraph_repo) if args.kgraph_repo else None,
        db_path=Path(args.db) if args.db else None,
        results_dir=RESULTS_DIR, max_turns=args.max_turns,
    )
    md, js = render.render(run_id, RESULTS_DIR, REPORTS_DIR)
    print(f"\n✅ run {run_id}\n   results: {RESULTS_DIR/run_id}\n   report:  {md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
