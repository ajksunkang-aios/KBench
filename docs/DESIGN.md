# KBench — 面向 OS 内核智能体工程的 AI 测试套

> **The SWE-bench for Operating Systems.**
>
> KBench 是业界首个面向 **OS 内核智能体工程(agent engineering for the OS kernel)** 的 AI 测试套。它收录覆盖多个工程垂域的真实内核任务,用于**评估基础模型 / 智能体在 OS 内核这类系统软件上的表现**,并**印证内核工程问题的复杂度**。本工作类比 [SWE-bench](https://swebench.com),定位为**操作系统领域的 SWE-bench**。

---

## 1. 一句话定位

KBench 是一个**与被测系统解耦**的、**多垂域**的内核智能体基准:给定真实内核工程任务(retrieval / MR-review / bugfix / patch backporting …)与各自的真值(ground truth),让基础模型或智能体系统求解,用**准确率 + 成本**(执行时间 / token / 工具调用)双维度评分,产出可上报、可对比的评估报告与榜单。

- **被评对象**:基础模型、智能体系统(如 KGraph 这类代码检索/推理系统)。
- **任务来源**:真实 Linux 内核工程场景。
- **真值**:上游事实(fix commit、review 意见、backport 补丁、编译器解析的检索集合)。
- **目标读者**:模型/agent 评测研究者、内核工程工具(如 KGraph)的构建者与使用者。

---

## 2. 为什么需要 KBench(动机)

1. **通用基准不覆盖内核**。SWE-bench 等主流基准以 Python 应用仓库为主,**几乎不触及 OS 内核**——而内核是系统软件中最复杂、约束最强(并发、架构相关、配置相关、间接调用、宏密集)的形态。
2. **基础模型在内核上的表现基本未知**。一个在 SWE-bench 上高分的模型,在内核 bugfix/review 上能否同样有效?目前没有标准化答案。KBench 填补这个空白。
3. **印证内核工程问题的复杂度**。KBench 的结果(与通用 SWE 任务的分数落差、以及模型在哪些子能力上系统性失败)将**实证内核是区别于通用软件工程的、更难的边疆**——这是 KBench 的研究叙事。
4. **为垂域智能体系统提供有效性验证基准**。构建内核智能体工具(如 KGraph)的团队,需要一个公认基准来证明"我的系统让 agent 在内核任务上做得更好"。KBench 是这个基准。

---

## 3. 三重目标

| 目标 | 含义 | KBench 如何体现 |
|---|---|---|
| **评估模型能力** | 基础模型/agent 在内核工程上到底行不行 | 各垂域准确率 + 成本 |
| **印证复杂度** | 内核比通用 SWE 更难 | 与通用基准的分数落差 + 失败模式分析(间接调用/并发/架构/配置) |
| **验证系统有效性** | 某个智能体系统(如 KGraph)是否提升了 agent 表现 | 系统级 A/B:有系统 vs 无系统 |

---

## 4. 与 SWE-bench 的类比与差异

| 维度 | SWE-bench | KBench |
|---|---|---|
| 领域 | 通用(Python 应用仓库) | **OS 内核(Linux)** |
| 任务来源 | 真实 GitHub issue + 解决 PR | 真实内核场景(fix commit / MR / backport / 检索) |
| 真值 | 解决 issue 的 PR + 仓库测试 | 上游事实(fix / review / backport / 编译器真值) |
| 评分 | 补丁是否通过仓库测试(行为级) | 行为级 + 语义级 + 集合级(按垂域) |
| 垂域 | 单一(修 issue) | **多垂域**(retrieval / MR-review / bugfix / backporting) |
| 难度根源 | 代码规模、跨文件理解 | **+ 间接调用、并发、架构相关、配置相关、宏密集** |
| 用途 | 评测模型 | 评测模型 **+ 验证智能体系统有效性** |

KBench = SWE-bench 的**内核垂域版 + 多任务类型 + 系统级 A/B**。

---

## 5. 垂域测试套(collection)

KBench 由多个**垂域测试套**组成,每个垂域有独立的任务形态、真值来源与评分口径:

| 垂域 | 任务形态 | 真值来源 | 准确率口径 |
|---|---|---|---|
| **retrieval**(代码检索) | 找 caller/callee、struct 字段、**间接调用解析(ops_bind)**、调用路径、引用、类型定义 | **编译器解析的确定集合** | recall / precision / 路径 IoU |
| **MR-review**(代码审查) | 给一个 patch/MR,挑出问题 | LKML / 修复 commit 反推的已知 review 意见 | 已知问题的 recall + 误报率(precision) |
| **bugfix**(缺陷修复) | 给 bug/崩溃报告,定位根因 + 出补丁 | 上游 `Fixes:` commit | 补丁是否修对(行为级)+ 语义匹配 |
| **patch backporting**(补丁回移) | 把新版本 fix 移植到旧版本 | stable 树的回移补丁 | 干净 apply + 语义匹配 |

> 各垂域**成本度量统一**(time / token / 调用次数),**准确率每个垂域一个 scorer**,报告一个公共格式。加新垂域 = 加一个 scorer,不动驱动器与报告。

### retrieval 在 v1 的特殊地位

retrieval 虽是垂域之一,但它是**最基础的一块**:它直接度量代码索引/查询能力,GT 最客观(编译器真值),且是其他垂域(bugfix/review 都要先检索相关代码)的基座。因此 **v1 先打通 retrieval 闭环**,再扩 bugfix / MR-review / backporting。

---

## 6. 评估方法

### 6.1 两种评测模式

- **系统级 A / B(验证系统有效性)**:同一个 agent + 同一个模型,只在"是否接入被测系统"上分臂。以 KGraph 为例:
  - Arm A — baseline:grep/ripgrep + 文件读取(无索引)
  - Arm B — + KGraph MCP(有索引)
  - 目的:证明"接入 KGraph 让 agent 在内核任务上更准/更省"。
- **纯模型上限(评估模型能力)**:不给外部工具,看裸模型在各垂域的上限分数。目的:建立"模型在内核上到底行不行"的基线,并与通用 SWE 基准对比(印证复杂度)。

### 6.2 控制变量(系统级 A/B)

同一模型、同一 temperature、同一工具中立系统提示、同一任务集、同一 prompt-cache 策略。**唯一变量 = 是否接入被测系统**。每任务每臂 **N≥3–5 次**,报中位数 + IQR。

### 6.3 度量

- **准确率**:每垂域自己的 scorer(§5)。
- **成本(全垂域统一)**:
  - **token 消耗**(in/out/cache,来自 API `usage`)—— 主成本指标(= 钱)
  - **工具调用次数**(按工具名分类)—— 辅助(= round-trip 数)
  - **执行时间**(wall-clock)—— 第三
- **联合**:准确率 × token 二维图,或"每答对一任务的成本"。

---

## 7. Ground truth 与评分(可信度核心)

- **真值独立于被测系统**:retrieval 的真值是编译器解析集合,**不能直接取自 KGraph 输出**(否则循环论证)。每任务从源码 + 编译事实独立核验一份真值,并对样本交叉验证。
- **诚实分层(retrieval)**:直接检索(direct caller / 字段 / 引用)grep 也能找全 → 差距主要在**成本**;编译器感知检索(**ops_bind / 间接调用 / 多跳路径 / 宏展开**)grep **准确率本身 <100%** → 差距在**准确率**。报告分层呈现,不混为一谈。
- **行为级优先(bugfix)**:能用"补丁是否让崩溃/测试消失"判的,不用纯文本相似度。

---

## 8. 数据 Schema

### 任务 `tasks/<vertical>/<id>.json`

```json
{
  "id": "retrieval/ops_impls/read_iter-ext4",
  "vertical": "retrieval",
  "subtype": "ops_impls",
  "repo": "/path/to/linux",
  "base_commit": "<sha>",
  "prompt": "Which functions are bound to file_operations.read_iter in ext4?",
  "ground_truth": { "method": "set", "expected": [["ext4_file_read_iter","fs/ext4/file.c"]] },
  "scorer": "set_recall_precision"
}
```

### 结果 `results/<run-id>/<vertical>/<id>.json`

```json
{
  "run_id": "2026-06-14T10-armB",
  "task_id": "retrieval/ops_impls/read_iter-ext4",
  "vertical": "retrieval",
  "arm": "B-kgraph",
  "model": "claude-...",
  "replicate": 2,
  "accuracy": {"recall": 1.0, "precision": 1.0, "f1": 1.0},
  "cost": {"tokens_in": 1234, "tokens_out": 567, "tokens_cache": 8900,
           "tool_calls": {"grep": 0, "find_ops_impls": 1},
           "wall_seconds": 4.2}
}
```

---

## 9. 报告与榜单(供显示上报)

报告是 KBench 的**对外产物**,分两层:

- **结构化 JSON**(机器读,喂看板/榜单):每 `(vertical, subtype, arm/model, task)` 一行 → 时序存储。
- **可读渲染**(Markdown / HTML):
  - **总览榜**:各模型/系统在每垂域的准确率 + 平均成本。
  - **垂域对比**:系统级 A/B 的准确率与成本表。
  - **复杂度证据页**:与通用 SWE 基准的分数落差 + 失败模式分析(模型在 indirect-call / 并发 / 架构 / 配置上系统性失败的分布)。
  - **亮点页**:retrieval/ops_impls 这类 grep 盲区的准确率碾压对比。

命令:`kbench run` / `kbench report <run-id>`。

---

## 10. 集成方式

KBench 是独立基准仓;被测系统(如 KGraph)在**自己的 eval workflow 里显式 `git clone` KBench**(钉 tag/commit 保可复现,**不上 submodule**):

```yaml
- run: git clone --depth 1 --branch <tag> https://github.com/ajksunkang-aios/KBench.git kbench
- run: kbench run --mode system-ab --system kgraph --verticals retrieval --repo <linux>
- run: kbench report <run-id>
```

---

## 11. 分期路线

**v1 — retrieval 核心闭环(本轮)**
1. 目录/schema:`tasks/retrieval/`、`scorers/`、`harness/`、`report/`。
2. 任务集:先策展 retrieval 的 3 个子类(**ops_impls ★ + callers + struct_layout**),每类 ~10–15 条,人工核验 GT。
3. 驱动器:单臂单任务跑通(Arm A baseline),证明 harness 成立。
4. 系统级 A/B 接入 KGraph,出第一版报告。

**v2 — 垂域扩展**
- bugfix(SWE-bench 式:真实 issue → fix,行为级评分)→ MR-review → patch backporting。
- 复用 v1 的成本度量与报告管线,每垂域加一个 scorer + 任务集。
- 上"纯模型上限"模式,产出与通用 SWE 基准的对比(复杂度证据)。

---

## 12. 严谨性红线(决定数字有没有人信)

1. **Determinism**:N≥3 次,报中位数 + IQR(不可妥协)。
2. **臂公平**:工具中立提示;两臂工具描述质量相当。
3. **GT 非循环**:真值独立于被测系统,人工核验 + 样本交叉验证。
4. **任务选择**:诚实包含 baseline 本就够用的子任务,别让全集偏向被测系统。
5. **缓存对齐**:各臂 prompt-cache 策略一致。
6. **可复现**:钉 KBench commit + 固定模型版本 + 记录每次 run 环境。

---

## 13. 目录结构(建议)

```
KBench/
  docs/DESIGN.md                 # 本文件
  tasks/
    retrieval/   {ops_impls,callers,struct_layout,...}/<id>.json
    mr-review/   ...
    bugfix/      ...
    backporting/ ...
  scorers/        set_recall_precision.py / path_iou.py / patch_apply.py / ...
  harness/        driver.py(模式:system-ab / model-only) arms.py(工具装配)
  report/         aggregate.py  render.py
  kbench/         CLI: run / report / leaderboard
  results/        run 产物(gitignore)
  reports/        报告产物
```

---

*KGraph 是 KBench 上首批被验证的系统之一;但 KBench 本身是模型/系统无关的——它是操作系统领域的 SWE-bench。*
