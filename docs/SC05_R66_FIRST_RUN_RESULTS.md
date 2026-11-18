# R6.6-A · 独立论文检索实测结果（2026-11-18）

> 状态：**检索已运行，完整性未通过；需人工复核与领域/方法双通道调整**。  
> 不是 DeepSeek 科研报告 A/B，不是经过双人裁决的黄金标准结果。

| 待解决问题 | 方法 | 实验内容 | 状态 | 简要结果 | 后续 | 详细记录 |
|---|---|---|---|---|---|---|
| R6.5 的同领域筛选是否会误把跨学科方法类比当成真实轨道交通近邻？ | 单独已发表论文 + 15 条 DOI 暂定银标准 + 真实 OpenAlex 摘要 + 固定筛选器 | 四次云端 DOI 试验，每次15次 OpenAlex 请求，0次DeepSeek | **部分完成／待复核** | OpenAlex有效摘要14/15；领域精确率4/7=57.1%，已解析同领域召回4/4=100%；跨域方法3/5仍被接纳；无关论文0/4被接纳 | 第二评审确认银标准、另设开发集实现方法迁移通道，再用新的留出论文检验 | 本页、GitHub Actions artifact、benchmarks/results/sc05_r66_20261118_summary.json |

## 1. 原始实验与运行证据

预登记：docs/SC05_R66_HELDOUT_EVAL_PLAN.md（先写入 GitHub，再获得真实筛选结果）。

- 留出论文：Wang et al. (2026), DOI 10.1038/s41598-026-67177-7；2026-09-16 发表于 Scientific Reports，官方 DOI：https://doi.org/10.1038/s41598-026-67177-7。
- 发表来源核对的候选 DOI 15 条；包含源论文自身用于测试禁止自引。
- 云端实际执行1：GitHub Actions run 44331917049，artifact 14439581879。
- 云端实际执行2：GitHub Actions run 44331899054，artifact 14439682028。
- 文档同步重复触发3：GitHub Actions run 44332784187，artifact 14439862124。
- 文档同步重复触发4：GitHub Actions run 44332939106，artifact 14440990333。
- 四次运行的指标和每个 DOI 的筛选决定一致（后两次由 PR 文档更新触发，已修复重复触发规则）。
- 每次15次**公开 OpenAlex DOI 元数据请求**，从未调用 DeepSeek；四次合计60次检索请求。初始工作流同时监听 push/PR 及文档修改，导致重复运行；现已改为新评测PR首次提交或显式手动触发。
- GitHub Actions 离线测试通过。实时检索步骤使用 strict-coverage，因 1 篇缺摘要，退出码2；工作流为非阻断模式，不能将整体绿色标志误读为实时证据质量已通过。
- 结果只保存标题、DOI、摘要 SHA-256、初标类别、筛选决定和隔离原因，不保留全文、PDF或原始摘要。

## 2. 指标（仅用有摘要的14条计算）

| 指标 | 结果 | 解读 |
|---|---:|---|
| 元数据可用率 | 14/15 = 93.3% | 1 篇 OpenAlex 缺摘要，未被当作负例 |
| 同领域候选召回率（暂定标签） | 4/4 = 100% | 2 篇直接近邻 + 2 篇背景均被保留；另 1 篇直接近邻无法核验 |
| 同领域候选精确率（暂定标签） | 4/7 = 57.1% | 被保留的7篇里3篇是跨领域方法候选 |
| 无关学科误收率 | 0/4 = 0% | 选入的生态/化学/微血管等4篇均被隔离 |
| 跨领域方法隔离率 | 2/5 = 40% | 3篇虽然可能有方法启发，但被误混入同领域候选池 |
| 源论文本身 | 1/1 被排除 | 自引不能被记作独立先例 |
| 真实最近先例机制准确率 | 未测 | 需要完整的“论文—诊断—竞争机制”评审 |
| 科学选题新颖性 | 未认证 | 不可由 DOI 过滤或摘要逐字匹配来推断 |

## 3. 需关注的具体记录

**OpenAlex 无摘要，但出版商有文章说明**：

- DOI 10.1016/j.trd.2024.104587：Resilience assessment of an urban rail transit network under natural disasters。
- 此记录标记为 abstract_unavailable，不伪造摘要、不把数据缺失解释为不存在相关研究。
- 官方出处：https://doi.org/10.1016/j.trd.2024.104587。

**需要独立第二评审判断是否属于直接先例（目前标签为方法迁移）**：

1. DOI 10.1038/s41467-025-63001-4：A small set of critical hyper-motifs governs heterogeneous flow-weighted network resilience。
2. DOI 10.1038/s42005-024-01664-z：Dimension reduction approach for understanding resource-flow resilience to climate change。
3. DOI 10.1038/s41598-024-54104-x：The connectivity indices concept of neutrosophic graph and their application of computer network, highway system and transport network flow。

这些文章不必被删除；它们可能贡献算法或网络分析方法。当前问题是它们**还没有证据可直接充当轨道交通的最近机制先例**。现有检索器的同领域关键词规则较宽，未能将这种方法启发与直接机制竞争分开。下游 closest-paper 规则仍有更严格的摘要/诊断关系筛选，但本轮没有测试其真实准确率，因此不能说这些3篇一定已经污染最终报告。

## 4. 结论及后续科研工程动作

- 已实际验证：真实 OpenAlex 接口可调用、源论文能自排除、无关学科负例基本被隔离、相同输入下重复结果稳定。
- **未通过完整科研质量门槛**：1篇真实相关论文的摘要缺失，3篇跨领域方法仍进入同领域候选；银标准没有第二评审。
- 下一阶段 R6.7 应增加可追溯的 domain_nearest / method_transfer_candidate 双通道，不应把跨领域创新方法简单删掉，也不能把跨域类比当作最近实证先例。
- **严格防止测试集泄漏**：这15条 DOI 已作为 R6.6-A 测试数据暴露，不能在针对它们修复后又宣称在“未见过的 R6.6 数据”上通过。后续开发要使用另一份 development set，并对新论文留出全新的测试集。
- 下一篇独立论文的真实 DeepSeek 研究工作流需要明确授权；本次实验没有启动付费 A/B。

保留原始 Run、Artifact 与 PR 溯源，不修改 R6.4.5 的70/38分、原论文 SHA 或历史检查点。
