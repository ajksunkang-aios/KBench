#!/usr/bin/env python3
"""
Import the CVE patch dataset (../patch_dataset/linux/<CVE>/) into KBench as
backport tasks.

Each CVE dir contains:
  <tag>.yml (or config.yml)   — metadata: new_patch (upstream fix commit),
                                new_patch_parent, target_release (older kernel
                                to backport INTO), tag.
  <tag>.patch (or real.patch) — the upstream fix patch (ground truth).
  build.sh                    — how to build the affected module.
  test.sh                     — kunit test that verifies the fix.
  <tag>.config / .kunitconfig — kernel configs for the test (referenced by path,
                                not vendored — too large).

Output: tasks/backport/<CVE>.json in KBench's task schema, extended for backport
(upstream/target commits, inline fix patch, build/test cmds, dataset_dir ref).
The backport harness (checkout target → apply agent patch → build → kunit) is a
follow-up; this script only ports the dataset.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# repo root = KBench/
_REPO = Path(__file__).resolve().parent.parent
DATASET = Path("/Users/ajksunkang/workspace/patch_dataset/linux")
LINUX_REPO = "/Users/ajksunkang/workspace/linux"
OUT_DIR = _REPO / "tasks" / "backport"


def _read_yml(p: Path) -> dict:
    """Parse a flat key: value YAML."""
    d = {}
    for line in p.read_text().splitlines():
        line = line.rstrip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, _, v = line.partition(":")
        d[k.strip()] = v.strip()
    return d


def _first(globs: list[str], dir: Path) -> Path | None:
    for pat in globs:
        m = sorted(dir.glob(pat))
        if m:
            return m[0]
    return None


def import_one(cve_dir: Path) -> dict | None:
    yml_p = _first(["*.yml", "*.yaml"], cve_dir)
    patch_p = _first(["*.patch", "*.diff"], cve_dir)
    build_p = _first(["build.sh", "build_*.sh"], cve_dir)
    test_p = _first(["test.sh", "test_*.sh"], cve_dir)
    if not yml_p or not patch_p:
        print(f"  skip {cve_dir.name}: missing yml/patch", file=sys.stderr)
        return None

    meta = _read_yml(yml_p)
    tag = meta.get("tag") or cve_dir.name
    patch = patch_p.read_text()
    build = build_p.read_text().strip() if build_p else ""
    test = test_p.read_text().strip() if test_p else ""

    return {
        "id": f"backport/{tag}",
        "vertical": "backport",
        "subtype": "cve",
        "tag": tag,
        "repo": LINUX_REPO,
        # target_release = the OLDER kernel to backport the fix INTO.
        "base_commit": meta.get("target_release", ""),
        "upstream_fix_commit": meta.get("new_patch", ""),
        "upstream_fix_parent": meta.get("new_patch_parent", ""),
        # the upstream fix patch, inlined (self-contained "here is the fix to backport").
        "upstream_fix_patch": patch,
        "prompt": (
            f"Backport the following upstream Linux kernel fix (commit "
            f"{meta.get('new_patch','')[:12]}) to the kernel at commit "
            f"{meta.get('target_release','')[:12]}.\n\n"
            "Produce a patch that applies cleanly to the target kernel and preserves "
            "the fix. Return the patch in a fenced ```diff block.\n\n"
            f"Upstream fix patch:\n```diff\n{patch}\n```"
        ),
        # build/test for behavioral verification (future harness).
        "build": build,
        "test": test,
        # large configs stay in the source dataset; referenced by path.
        "dataset_dir": str(cve_dir),
        "ground_truth": {"method": "patch_apply", "patch": patch,
                         "build": build, "test": test},
        "scorer": "patch_apply",
    }


def main() -> int:
    if not DATASET.is_dir():
        print(f"ERROR: dataset not found: {DATASET}", file=sys.stderr)
        return 2
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    for cve_dir in sorted(p for p in DATASET.iterdir() if p.is_dir()):
        task = import_one(cve_dir)
        if not task:
            continue
        out = OUT_DIR / f"{task['tag']}.json"
        out.write_text(json.dumps(task, indent=2))
        print(f"  {task['tag']:18s} target={task['base_commit'][:10]} "
              f"fix={task['upstream_fix_commit'][:10]} patch={len(task['upstream_fix_patch'])}B")
        n += 1
    print(f"\nimported {n} backport tasks → {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
