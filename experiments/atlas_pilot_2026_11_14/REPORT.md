# Research Atlas 三来源发现实验：OpenAlex 与期刊官网核查

**实验日期：** 2026-11-14  
**状态：** 已完成一次真实 OpenAlex API 采集、期刊官网/网页检索哨兵核查及针对性漏检排查；**尚未运行生产 GPT API 的 web_search 和自动 L1 科研生成**。  
**执行：** [真实采集与九篇对照](https://github.com/Hu-py/research-opportunity-workbench/actions/runs/43552802805)；[四篇漏检定向诊断](https://github.com/Hu-py/research-opportunity-workbench/actions/runs/43552898864)。  
**代码：** [草稿 PR #57](https://github.com/Hu-py/research-opportunity-workbench/pull/57)；本轮未更改主分支、线上周报及数据库。

## 1. 问题与对照设计

目标是判断 **OpenAlex 结构化采集能否覆盖各来源官网近期论文，网站/模型联网检索应在哪一步补充**；并检验“论文可检索到”与“论文研究结论可信”是否得到明确区分。

三个来源各选一处：A 为 *Sustainable Cities and Society*（SCS），B 为 *Environment and Planning B: Urban Analytics and City Science*（EPB），C 为 *Journal of Machine Learning Research*（JMLR）。以各官网公开可核查的三篇论文组成 **9 篇哨兵样本**（名单与链接见 [official_sentinels.json](./official_sentinels.json)）。这些论文由定向网页搜索和官方网站核验得到，**并非从期刊某个时间窗完整枚举**，所以不能把命中率称为“期刊总召回率”，也不能把 9/9 当成 GPT API 检索性能。

OpenAlex：以期刊来源 ID 按 `primary_location.source.id` 检索，窗口固定 2026-09-15 至 2026-11-14，**每个来源最多返回 100 篇**；结果保留原始工作 ID、来源和摘要等级。随后对未命中的四篇进行单独 DOI/标题检索，帮助判断是不存在、时间问题、来源问题还是截断问题。

## 2. 本次真实结果

| 来源 | 60 天按期刊采集 | 官网哨兵样本命中 | 解释 |
| --- | ---: | ---: | --- |
| A · SCS | **100** 篇 | **2/3** | OpenAlex 该期刊该窗口实际索引计数为 **185**，首批仅取最近 100 篇 |
| B · EPB | **23** 篇 | **3/3** | 三篇 2026 年 11 月初发表的官网论文均命中 |
| C · JMLR | **0** 篇 | **0/3** | 以 JMLR 作为 `primary_location` 的 60 天筛选结果为零 |
| **全局去重** | **123** 篇 | **5/9** | 只能说明一次有上限的来源检索对九篇选定样本的命中情况 |

**发现 1：SCS 的缺漏来自采样截断，不是 OpenAlex 没收录。** 漏掉的 [《Spatial structure associations and response-range mismatches between urban land surface temperature and urban vitality》](https://www.sciencedirect.com/science/article/pii/S2210670726008413) 的 DOI 为 `10.1016/j.scs.2026.107957`；定向 DOI 查询在 OpenAlex 找到 `W7214897818`，其 OpenAlex `publication_date` 为 **2026-09-30**，来源也是 SCS（`S163634330`）。因为该期刊近 60 天有 185 条记录，最近 100 条的分页上限使此篇被漏掉。**建议使用 cursor/分页检索所有目标窗口内的记录**，并把 `meta.count` 与返回数记录下来；不应将采样上限误读成该期刊只有 100 篇。

**发现 2：JMLR 的缺漏来自论文版本/来源归属，而非全局学术索引没有论文。** 官网 [2026 年第 27 卷目录](https://www.jmlr.org/papers/v27/) 包含选定的 #235、#236、#237 三篇文章。但通过精确标题再次查询 OpenAlex，可以找到对应的同名记录：

| 官网 JMLR 论文 | OpenAlex 发现的记录 | OpenAlex 首要来源 | 记录日期 |
| --- | --- | --- | --- |
| *A New Family of Poisson Non-negative Matrix Factorization Methods Using the Shifted Log Link* | `W7123290241` | arXiv | 2026-01-09 |
| *Bayesian Predictive Inference Beyond Martingales* | `W4415337375` | arXiv | 2025-07-29 |
| *CLASSIX: A High-Performance Library for Explainable Clustering* | `W7223514973` | HAL | 2026-10-21 |

这些检索结果**证明标题相关记录存在**，但**不能据此认定 OpenAlex 已将这些记录正确标记为 JMLR 2026 期刊正式版本**。因此使用单一的 `primary_location.source.id=JMLR` 加近期 `publication_date` 会把当前部分正式发表文章漏掉；仅依靠 arXiv 日期，也会把较早预印本误判为不是新出版研究。下一步应以 **出版商目录/正式期刊页面** 确认发表身份，以 DOI/标题/作者和版本关系连接 arXiv、HAL 与正式发表，分别记录 `preprint_date`、`journal_first_online_date`、`index_publication_date`、`first_discovered_at`。

**发现 3：EPB 按来源筛选本轮命中较好，但仍不能推断长期完整性。** 选定的官网 11 月 2 日、5 日、7 日三篇均被采集，OpenAlex 提供了摘要；不代表同刊在更长时间或其他版本的全部作品都已收录。

**数据与审查边界：** 收录范围和论文索引随时间变动；官网 SCS 的另两篇显示的是 **2026-11-01 期刊卷期日期**，不能冒充首次在线日期。JMLR 官网目录在本次查看中没有为三篇指定可统一比较的 first-online 日期，因此 C 的“60 天官网发表召回率”不能估算。OpenAlex `status=complete` 在当前代码中表示请求执行完毕，**不意味着期刊数据没有缺漏**。

## 3. 研究理解示范：网页定向补证据（不是自动 Agent 通过验收）

### A · 一个可成立的 L1 主题候选：城市活力的测量、依赖结构与热环境目标

同一期 SCS 的两篇文章提供不同而可对照的研究进展：

1. [Jia 等：Learning dependency structures of urban vitality at the census-block level](https://www.sciencedirect.com/science/article/pii/S2210670726008851) 结合街景目标识别和 POI 构造城市活力指标，并用贝叶斯网络检查街区因素与活力的**条件依赖**。其结果在曼哈顿数据上强调社会空间因素和道路网络密度，但不能自动解释为已验证的因果机制。
2. [Zhang 等：Spatial structure associations and response-range mismatches between urban land surface temperature and urban vitality](https://www.sciencedirect.com/science/article/pii/S2210670726008413) 在合肥 500 米网格上把地表温度与相对活力作为两个响应，在统一空间单元中比较 XGBoost–SHAP 的变量贡献与响应阈值；结果强调热与活力的响应节点未必一致。

**合理的跨论文综合：** 这两篇不是一个新算法的重复验证；前者研究城市活力内部的因素依赖，后者研究活力与热环境之间的多目标关系。可向规划团队推荐的**学习动作**是核查不同城市活力代理指标、空间尺度和估计目标能否兼容，然后探索多目标空间策略，但当前两篇不能单独证明“全领域方法趋势”或“因果机制”。

### B · 代表性单篇观察：预测不确定性不等于校准可靠性

[Larraín 等：Quantifying uncertainty in deep learning models for urban safety perception](https://journals.sagepub.com/doi/10.1177/23998083261504070) 将 MC Dropout 引入城市安全感知预测。作者明确指出其研究**尚未验证不确定性与真实预测误差之间的校准或可靠性排序关系**。因此 Research Atlas 不能将“模型输出了置信区间或不确定性”直接包装为“已解决空间预测可信度问题”。这条单篇提示可作为 L2 深读或研究审查负面案例，而不是硬凑入多论文趋势。

### C · 代表性技术观察：可解释聚类工具

[JMLR：CLASSIX — A High-Performance Library for Explainable Clustering](https://www.jmlr.org/papers/v27/26-1057.html) 给出开放 Python 聚类实现。它可能值得团队测试，用于道路、街区或城市类型的无监督划分；但需要另行评估空间连续性约束、稳定性以及与已有 GIS 聚类/区域化方法的对照。当前不能因为工具开源且可解释就推断其一定优于团队现用方法。

**说明：** 以上为本轮 ChatGPT 辅助官网证据阅读的**示范性科研综合**，并非已通过自动 Research Atlas L1 工作流的输出，也尚未进行两位领域专家的 Gap/技术新颖性复核。

## 4. 对技术架构的直接修改建议

**保留学术 API 基础库，但增加两级补采策略：**

`A/B/C 来源目录 → 学术 API 全窗口分页召回 → DOI/标题补检 → 官方期刊目录与版本校验 → 候选论文/证据仓 → LLM 多论文综合 → 人工审查`

- **基础扫描：** OpenAlex 按可配置来源查询，但要记录 `meta.count`、分页进度、查询时间窗、无结果来源、摘要可用性，采样上限不能默认为完整覆盖。
- **官网补充：** 对重要期刊的最新目录、索引返回零、来源身份不一致和团队高优先主题，使用期刊官网、官方 RSS/出版商 API、必要时经授权的 GPT 网页搜索，获得**正式出版身份**与 DOI/文章 URL。不是按 GPT/DeepSeek 品牌自动切换，工具应独立于模型。
- **预印本关联：** arXiv/HAL 先作为论文版本，而不是一篇新增正式会议/期刊论文；对同题不同版本核查作者及正式页面后归并，记录首次出现与正式出版两个时间。
- **真实科研评估：** 下一次在相同论文集合上对比通用 LLM、当前 Atlas L1 与改造后 L1；评价多篇综合、Gap 依据、方法辨析、审查边界和推荐价值，不能以成功检索篇数替代。
- **进入生产的门槛：** 本次仅单次 3 期刊、9 哨兵、有限时间窗测试；扩展到多期刊、包含完整官方目录的固定测试窗，并核实检索成本后，再决定各类来源的主/补渠道及删减旧 Radar 采集器。

## 5. 可复现资产

- [实验用 A/B/C 单期刊来源配置](./source_plan.json)
- [九篇来自官网的哨兵论文清单](./official_sentinels.json)
- [自动比较脚本](./evaluate.py)
- [遗漏原因 API 诊断脚本](./probe_missing.py)
- [首次真实运行与采集结果工件](https://github.com/Hu-py/research-opportunity-workbench/actions/runs/43552802805)
- [漏检诊断运行与工件](https://github.com/Hu-py/research-opportunity-workbench/actions/runs/43552898864)

所有原始数据工件为 GitHub Actions 有时限的实验附件；该实验报告与输入、运行配置在 Draft PR 分支，不改变正式生产配置。
