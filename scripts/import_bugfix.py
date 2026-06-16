#!/usr/bin/env python3
"""
Import the **already-crawled** syzkaller bugfix data into KBench as the bugfix
vertical — raw-file directories (not JSON), mirroring the backport layout.

Source: kernelcompass/benchmark_experiments/dataset/kernel_bench_data.json — a
JSON array of fully-crawled syzkaller bug instances. Each entry already has,
inline (no network needed):
  instance_id, repo, base_commit, base_config (.config), crash_report_data
  (the syzkaller crash report — the agent's input), ground_truth_patch (the fix),
  parent_commit, oracle_files, oracle_methods.

Output: one dir per bug at tasks/bugfix/<instance_id>/:
  meta.yml     instance_id, repo, base_commit, parent_commit, oracle_files,
               oracle_methods
  crash.txt    the syzkaller crash report           (agent INPUT)
  config       the kernel .config for reproduction  (~240 KB; for behavioral eval)
  patch        the upstream fix diff                (ground truth)

Usage:
    python scripts/import_bugfix.py [--src <kernel_bench_data.json>] [--n 20]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
DEFAULT_SRC = Path("/Users/ajksunkang/workspace/kernelcompass/benchmark_experiments/dataset/kernel_bench_data.json")
DEFAULT_OUT = _REPO / "tasks" / "bugfix"


def _yaml_list(items) -> str:
    if not items:
        return "[]"
    return "[" + ", ".join(json.dumps(str(i)) for i in items) + "]"


def import_one(e: dict, out_root: Path) -> str:
    bid = e["instance_id"].strip()
    bdir = out_root / bid
    bdir.mkdir(parents=True, exist_ok=True)

    base = (e.get("base_commit") or "").strip()
    parent = (e.get("parent_commit") or "").strip()
    (bdir / "meta.yml").write_text(
        f"id: {bid}\n"
        f"repo: {e.get('repo','')}\n"
        f"base_commit: {base}\n"
        f"parent_commit: {parent}\n"
        f"oracle_files: {_yaml_list(e.get('oracle_files'))}\n"
        f"oracle_methods: {_yaml_list(e.get('oracle_methods'))}\n"
    )
    (bdir / "crash.txt").write_text(e.get("crash_report_data") or "")
    (bdir / "config").write_text(e.get("base_config") or "")
    (bdir / "patch").write_text(e.get("ground_truth_patch") or "")
    return bid


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=str(DEFAULT_SRC))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--n", type=int, default=0, help="subset size (0 = all)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)

    src = Path(args.src)
    if not src.is_file():
        print(f"ERROR: source not found: {src}", file=sys.stderr)
        return 2
    data = json.loads(src.read_text())
    if not isinstance(data, list) or not data:
        print(f"ERROR: expected a non-empty JSON array in {src}", file=sys.stderr)
        return 2

    if args.n and args.n < len(data):
        random.seed(args.seed)
        data = random.sample(data, args.n)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"importing {len(data)} bugfix tasks → {out} (raw-file dirs, fully populated)")
    n = 0
    for e in data:
        if not e.get("crash_report_data") or not e.get("ground_truth_patch"):
            print(f"  skip {e.get('instance_id','?')[:12]}: missing crash/patch")
            continue
        bid = import_one(e, out)
        of = e.get("oracle_files") or []
        print(f"  {bid[:12]}  base={(e.get('base_commit') or '')[:10]}  "
              f"oracle_files={of}  crash={len(e.get('crash_report_data') or '')}B")
        n += 1
    print(f"\nimported {n} bugfix tasks → {out}")
    print("each dir: meta.yml + crash.txt (agent input) + config + patch (GT)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
