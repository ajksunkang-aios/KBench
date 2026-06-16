# KBench

> **The SWE-bench for Operating Systems.**
> The first AI test suite for **OS-kernel agent engineering**.

[English](README.md) · [中文](README.zh-CN.md)

KBench is an evaluation benchmark that measures how well foundation models and
AI agents perform on **real Linux-kernel engineering tasks**. It collects task
suites across multiple engineering verticals — code retrieval, MR review, bug
fixing, patch backporting — each with independently verified ground truth, and
scores systems on **accuracy** and **cost** (wall-time, tokens, tool calls).

Inspired by [SWE-bench](https://swebench.com), KBench brings the same
"real task → ground-truth solution → behavioral scoring" methodology to the
kernel — and goes further by spanning **multiple task types** and validating
whole agent **systems**, not just models.

## Why KBench?

- **General benchmarks skip the kernel.** Mainstream SE benchmarks target
  Python app repos; the kernel — the most constrained system software
  (concurrency, architecture-dependence, config-dependence, indirect calls,
  macro density) — is largely unmeasured.
- **How good are foundation models on the kernel?** A model that aces
  SWE-bench may still struggle on kernel tasks. KBench makes this measurable.
- **It demonstrates kernel complexity.** Score gaps versus general SE
  benchmarks, plus failure-mode analysis, empirically establish the kernel as
  a distinct, harder frontier.
- **It validates agent systems.** Teams building kernel-agent tools
  (e.g. [KGraph](https://github.com/ajksunkang-aios/KGraph)) need a shared
  benchmark to prove their system makes agents better. KBench is that benchmark.

## Evaluation verticals

| Vertical | Task | Ground truth | Accuracy |
|---|---|---|---|
| **Code retrieval** | find callers/callees, struct fields, indirect-call resolution (ops tables), call paths, references, type defs | compiler-resolved sets | recall / precision / path IoU |
| **MR review** | review a patch / merge request, surface issues | known review findings (LKML / fixing commits) | issue recall + false-positive rate |
| **Bugfix** | given a bug/crash report, locate root cause + produce a patch | upstream `Fixes:` commit | behavioral (does it fix it?) + semantic |
| **Patch backporting** | port a fix to an older version | stable-tree backport | clean apply + semantic match |

> Cost metrics are uniform across verticals (wall-time / tokens / tool-call
> counts); each vertical has its own accuracy scorer. Adding a vertical =
> adding one scorer — the driver and reports stay the same.

## How it works

KBench gives an agent (model + optional tooling) a real kernel task and scores
its output against ground truth. Two evaluation modes:

- **System-level A/B** — same agent + model, varying *only* whether the
  system-under-test is attached (e.g. with vs. without KGraph). Validates
  whether a system helps agents do better.
- **Model-ceiling** — no external tools; measures a model's raw ceiling per
  vertical, for cross-benchmark comparison and complexity evidence.

Outputs: structured JSON (for dashboards) + rendered leaderboard-style reports.

## Status

🚧 **In development.**

- **Code-retrieval vertical — functional v1.** A/B harness (baseline
  `grep/glob/read` vs `+KGraph`), tool-using agent loop, and accuracy+cost
  reports. Pinned to a fixed kernel commit (`v7.1-rc7`); see
  [`tasks/retrieval/manifest.json`](tasks/retrieval/manifest.json) + the setup
  workflow (`scripts/setup_retrieval.sh`: `git checkout` → build `kgraph.db` → run).
- **Patch-backporting vertical — dataset imported** (21 CVE tasks); the
  behavioral harness (checkout target → apply → build → test) is in progress.
- **Bugfix vertical — dataset imported** (20 syzkaller tasks, raw-file dirs,
  fully populated: crash report + config + fix patch); harness reuses the
  retrieval agent loop + a patch/oracle scorer (see
  [`tasks/bugfix/README.md`](tasks/bugfix/README.md)).

Roadmap: bugfix & backport harnesses → MR review.

## Dataset sources

- **patch-backporting** — derived from the dataset of:
  > **PORTGPT: Towards Automated Backporting Using Large Language Models.**
  > IEEE Symposium on Security and Privacy (S&P), 2026.
- **bugfix** — derived from the dataset of:
  > **KGym: A Platform and Dataset to Benchmark Large Language Models on Linux
  > Kernel Crash Resolution.** NeurIPS, 2024.
  >
  > GitHub: `Kernel_Benchmark_C_Repro` (syzkaller crash reports + upstream fix
  > commits).

## Design

Full design and methodology: **[`docs/DESIGN.md`](docs/DESIGN.md)**.

## Related

- [KGraph](https://github.com/ajksunkang-aios/KGraph) — compiler-aware kernel
  code-graph engine; one of the first systems validated on KBench.

## License

[MIT](LICENSE).
