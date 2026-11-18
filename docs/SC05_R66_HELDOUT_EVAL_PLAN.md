# Research Atlas · R6.6 独立论文检索验证（预注册）

更新：2026-11-18
分类：◇03 · 独立证据质量评测
既有基线：R6.4.5 (真实单论文 A/B) → R6.5 (领域近邻修复)

| 待解决问题 | 方法 | 实验内容 | 状态 | 简要结果 | 后续 | 详细记录 |
|---|---|---|---|---|---|---|
| 单篇 A/B 不能证明跨论文检索质量，历史检索混入哲学与语言学 | 换一篇独立已发表论文，预先冻结可追溯 DOI 标签，并评估现有过滤器 | 15项：直接近邻3、领域背景2、跨领域方法5、无关4、源论文1 | R6.6-A 基准/CI核验中 | **暂不能声称质量提升**，标签仍是单人暂定银标准 | DOI 元数据检索→人工双评→必要时进一步真实 A/B | benchmarks/sc05_r66_silver_set_v01.json + scripts/sc05_r66_eval.py |

## 1. 选用独立论文

Wang et al. 2026, "Quantifying temporal vulnerability of urban multi-modal transit networks under interdependent cascading failures", Scientific Reports, DOI: 10.1038/s41598-026-67177-7。出版日期2026-09-16。官方来源：https://www.nature.com/articles/s41598-026-67177-7

- 与 R6.4.5 使用的 Shen et al. 2026 TRD 是两篇不同论文；选择发生在 R6.6 测量前。
- 只验证相近的轨道交通/多模式网络领域可迁移性，**不宣称已验证跨领域科研发现能力**。
- 这是对旧 A/B 流程未使用过的论文，但评审者已知其题目，不能冒称严格双盲。
- 本阶段不将整篇论文 PDF/原文保存到 GitHub，也不运行 DeepSeek。

## 2. 冻结银标准

文件：benchmarks/sc05_r66_silver_set_v01.json

- direct_near（3）：同研究对象且可能涉及可比较的网络容量、扰动、客流与韧性机制；
- domain_context（2）：同领域综述/背景研究，尚不是直接机制竞争先例；
- method_transfer（5）：跨领域方法启发，需要数据映射和适用性验证；
- unrelated（4）：非城市轨道交通机制，不得作为直接近邻；
- source_self（1）：留出论文自身，不可充作独立近邻。

每条均附 DOI、正式标题、出版年份、判断理由及 DOI 链接。初始判断仅依赖出版方题目与摘要核查，属于 provisional_silver_not_gold：至少需要另一位独立评审才有望形成可信黄金标准。不根据模型结果反向更改标签。

## 3. 预注册问题与工程验收指标

核心问题：R6.5 能否保留真正同领域的研究，同时隔离明显不相关学科，保留跨领域方法的审计线索？

预先提出的工程期望：
1. 领域近邻+同领域背景召回率 >= 0.80；
2. 明确无关文献的直接接纳率 = 0；
3. 留出论文自引正确被隔离；
4. 跨领域方法候选即使被隔离，也保留 DOI 与撤销原因。

评估字段：metadata_coverage、domain_precision_provisional、domain_recall_provisional、direct_near_candidate_recall、unrelated_admission_rate、method_transfer_quarantine_rate、source_self_excluded。

领域匹配只是最低准入，不等于最近先例的实质机制判断；本轮不会评判最近先例语义准确率（null）或研究新颖性（false）。**筛掉文献越多，不自动代表科研质量越好**。

OpenAlex DOI 记录缺失、未有摘要、受限流时须标为 partial_provider_coverage_not_comparable，不能把不完整样本的高分称作通过。将来使用额外的专家标注争议负例核验。

## 4. 云端流程与成本

- 自动工作流：.github/workflows/sc05-r66-openalex-eval.yml（本 PR 自动触发，也支持 workflow_dispatch）
- 离线测试：tests/test_sc05_r66_eval.py、tests/test_sc05_relevance.py
- 实际元数据检查命令：

    python -m scripts.sc05_r66_eval --manifest benchmarks/sc05_r66_silver_set_v01.json --live --max-requests 16 --output artifacts/sc05_r66_retrieval_metrics.json --strict-coverage

- 使用公开 OpenAlex DOI 查询，HTTP 请求上限16次；无 DeepSeek 调用，无模型 Token 费用；不把 Render 密钥移动到 GitHub。
- 公开 API 拒绝匿名连接时，记录失败，不能伪造结果。
- 只将 DOI、标题、摘要 SHA256、筛选决定、隔离原因及汇总指标放入 Actions artifact（保留7天），不保存外部论文全文/原始摘要。
- GitHub CI 离线测试与实时 OpenAlex 检查是两种不同验收，实时调用失败不应被静态测试通过掩盖。

## 5. 双人评审与留出规则

评审 A/B 各自看真实的标题与摘要，不看模型决定，按研究对象、机制、指标、证据层级、时间先后标注。争议保存两份判断，再裁决成不可变 gold_v1。领域背景与跨领域方法应继续区分；对跨领域可迁移项须明确输入输出映射、机制桥接、替代方法和否决条件。

R6.6-A 完成后，再进入 R6.6-B 新论文真正科研工作流：需要将来源页面交给 Owner 服务创建独立案例，核对源 SHA，顺序 gate-off 和 gate-on，匿名评分再解盲。**新的付费 DeepSeek A/B 需要针对这一新论文另行授权**，不得沿用 R6.4.5 的历史付费授权。

## 6. 数据与标签限制

银标准由同一名辅助评审者初标，不是独立金标准，也不是定量证明 R6.5 相较旧系统改善的因果证据；若以后改变 DOI 清单、标签或阈值应另开 R6.6.x 版本，保留原提交哈希，不能覆盖本轮。
