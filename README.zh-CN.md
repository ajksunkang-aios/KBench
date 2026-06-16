# KBench

> **操作系统领域的 SWE-bench。**
> 业界首个面向 **OS 内核智能体工程** 的 AI 测试套。

[English](README.md) · [中文](README.zh-CN.md)

KBench 是一个评估基准,度量**基础模型与 AI 智能体在真实 Linux 内核工程任务上的表现**。它收录覆盖多个工程垂域的任务套——代码检索、MR 审查、缺陷修复、补丁回移——每个垂域都有独立核验的真值(ground truth),并按**准确率**与**成本**(执行时间、token、工具调用次数)双维度评分。

KBench 类比 [SWE-bench](https://swebench.com),把"真实任务 → 真值解 → 行为级评分"的方法论带到内核,并更进一步:**覆盖多种任务类型**,且验证整个智能体**系统**(而不仅是模型)。

## 为什么需要 KBench?

- **通用基准不覆盖内核。** 主流软件工程基准以 Python 应用仓库为主;而内核——约束最强的系统软件(并发、架构相关、配置相关、间接调用、宏密集)——几乎没人测。
- **基础模型在内核上到底行不行?** 一个在 SWE-bench 上高分的模型,在内核任务上未必同样有效。KBench 把这件事变得可量化。
- **印证内核工程问题的复杂度。** 与通用基准的分数落差 + 失败模式分析,实证内核是区别于通用软件工程的、更难的边疆。
- **验证智能体系统的有效性。** 构建内核智能体工具(如 [KGraph](https://github.com/ajksunkang-aios/KGraph))的团队,需要一个公认基准来证明"我的系统让 agent 在内核任务上做得更好"。KBench 就是这个基准。

## 评估垂域

| 垂域 | 任务 | 真值来源 | 准确率口径 |
|---|---|---|---|
| **代码检索** | 找 caller/callee、struct 字段、间接调用解析(ops 表)、调用路径、引用、类型定义 | 编译器解析的确定集合 | recall / precision / 路径 IoU |
| **MR 审查** | 审查一个 patch / 合并请求,挑出问题 | 已知 review 意见(LKML / 修复 commit 反推) | 已知问题的 recall + 误报率 |
| **缺陷修复** | 给定 bug / 崩溃报告,定位根因 + 出补丁 | 上游 `Fixes:` commit | 行为级(是否修对)+ 语义匹配 |
| **补丁回移** | 把新版本的 fix 移植到旧版本 | stable 树的回移补丁 | 干净 apply + 语义匹配 |

> 成本度量全垂域统一(执行时间 / token / 工具调用次数);每个垂域有自己的准确率 scorer。加垂域 = 加一个 scorer,驱动器与报告不动。

## 工作方式

KBench 给一个 agent(模型 + 可选工具)一个真实内核任务,把它的输出对照真值评分。两种评测模式:

- **系统级 A/B** —— 同一个 agent + 模型,只在"是否接入被测系统"上分臂(如:有 KGraph vs 无 KGraph)。验证某系统是否让 agent 表现更好。
- **纯模型上限** —— 不给外部工具,测裸模型在各垂域的上限,用于跨基准对比、印证复杂度。

产物:结构化 JSON(喂看板)+ 可读的榜单式报告。

## 状态

🚧 **开发中。**

- **代码检索垂域 —— v1 已可用。** A/B 对照 harness(基线 `grep/glob/read` vs `+KGraph`)、带工具的 agent 循环、准确率+成本报告。钉定在一个固定内核 commit(`v7.1-rc7`);见 [`tasks/retrieval/manifest.json`](tasks/retrieval/manifest.json) 与 setup 流程(`scripts/setup_retrieval.sh`:`git checkout` → 构建 `kgraph.db` → 跑检索)。
- **补丁回移垂域 —— 数据集已导入**(21 个 CVE 任务);行为级 harness(checkout 目标版本 → apply → build → test)开发中。
- **缺陷修复垂域 —— 数据集已导入**(20 个 syzkaller 任务,原始文件目录,已完整填充:崩溃报告 + config + 修复补丁);harness 复用检索的 agent 循环 + 补丁/oracle 打分器(见 [`tasks/bugfix/README.md`](tasks/bugfix/README.md))。

路线图:缺陷修复 & 回移 harness → MR 审查。

## 数据集来源

- **补丁回移(patch-backporting)** —— 改编自以下论文的数据集:
  > **PORTGPT: Towards Automated Backporting Using Large Language Models.**
  > IEEE Symposium on Security and Privacy (S&P), 2026.
- **缺陷修复(bugfix)** —— 改编自 `Kernel_Benchmark_C_Repro` 的 syzkaller bug 实例(syzkaller.appspot.com 崩溃报告 + 上游修复 commit)。

## 设计

完整设计与方法论:**[`docs/DESIGN.md`](docs/DESIGN.md)**。

## 相关

- [KGraph](https://github.com/ajksunkang-aios/KGraph) —— 编译器感知的内核代码图谱引擎;KBench 上首批被验证的系统之一。

## 协议

[MIT](LICENSE)。
