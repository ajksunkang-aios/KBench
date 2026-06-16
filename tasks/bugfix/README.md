# KBench bugfix vertical — dataset & harness design

Sykaller-style kernel bug fixing: given a crash report, diagnose the root cause
and produce a fix patch.

## Dataset (raw-file dirs, not JSON)

Each bug is one directory under `tasks/bugfix/<fix-commit-sha>/`, mirroring the
backport dataset layout (raw files, not a single JSON task):

```
tasks/bugfix/<instance_id>/
  meta.yml       instance_id, repo, base_commit, parent_commit, oracle_files,
                 oracle_methods
  crash.txt      syzkaller crash report        (the agent's INPUT)
  config         kernel .config for reproduction
  patch          the upstream fix diff         (ground truth)
```

**Source:** `../kernelcompass/benchmark_experiments/dataset/kernel_bench_data.json`
— 20 fully-crawled syzkaller bug instances (crash report + `.config` + fix patch +
oracle already inline, no fetch needed). Ported by `scripts/import_bugfix.py`
(all 20; `--n K` to subset, `--seed` for reproducibility).

## Harness design

Reuses the retrieval harness's primitives; adds a bugfix task loader + a patch
scorer.

```
                 ┌──────────────────────────────────────────────┐
  crash.txt ───▶ │ agent loop (reuse kbench/harness/agent.py)   │
  (input)        │  arms: A grep/glob/read  |  B + KGraph (13)  │
  kernel tree @  │  tools explore the tree at parent_of_fix      │ ──▶ proposed patch
  parent_of_fix  └──────────────────────────────────────────────┘
                                                                          │
                         ┌────────────────────────────────────────────────┴────┐
                         ▼                                                     ▼
              scorer: oracle IoU                                  scorer: behavioral (future)
              (proposed files/functions                           (apply patch → build → run repro
               vs meta.yml modified_files/functions)               → crash gone?)
```

- **Input:** the crash report (`crash.txt`) + the kernel tree checked out at
  `parent_of_fix_commit` (the state the fix applies onto).
- **Agent loop:** identical GLM tool-use loop as retrieval (`kbench/harness/agent.py`).
- **Arms:** identical — A-baseline (grep/glob/read) vs B-kgraph (+KGraph). KGraph's
  `find_callers`/`call_path`/`get_callchain` are exactly what helps map a crash
  call trace to the root-cause function.
- **Task prompt:** "Here is a syzkaller crash. Locate the root cause in the kernel
  source and produce a minimal fix patch. Return the patch in a ```diff block and
  list each file|function you changed in a ```kbench block."
- **Ground truth:** `patch` (the upstream fix) + `modified_files` /
  `modified_functions` (the oracle set).
- **Scorers:**
  - **oracle IoU** (fast, objective, v1): file-level + function-level overlap of
    the agent's changed set vs `meta.yml` (same recall/precision machinery as
    retrieval's `set_recall`).
  - **behavioral** (gold, future): `git -C <linux> checkout parent_of_fix` →
    `git apply` the agent's patch → `make` the affected module → run `repro.c`
    under `config` → crash gone? (mirrors the existing kGym
    `kernel_bench_evaluator.py` build+repro flow).
- **Cost metrics:** identical to retrieval (tokens / tool-calls / wall-time),
  so the A-vs-B report is directly comparable across verticals.

### Reuse vs new

- **Reuse:** `kbench/harness/agent.py` (GLM loop), `kbench/harness/arms.py`
  (grep/glob/read + KGraph tools), `kbench/scorers/set_recall.py` (set IoU),
  `kbench/report/render.py` (A-vs-B + tier report).
- **new:** a bugfix task loader (reads `meta.yml` + `crash.txt` per dir), a
  `patch_apply`/behavioral scorer, and the `fetch_bugfix_assets.py` step.

## Status

Dataset staged (20 tasks, fully populated: crash.txt + config + patch). Harness
build (loader + scorer + wire into `kbench run --vertical bugfix`) is the next
step.
