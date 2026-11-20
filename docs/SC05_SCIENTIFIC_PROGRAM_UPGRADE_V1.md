# Research Atlas · SC05 科研能力升级 V1.0
**2026-11-20 · 单次集成升级，不启动新的付费 DeepSeek 实验**

> 目标是提高“发表论文 → 新科学问题 → 跨期刊理论和方法互补 → 独立论文研究议程”的能力，而非让原论文的指标审核清单变长。原 R6.4.5 的 38/70 盲评保留，**不能用本次工程改造追溯改变历史科研质量**。

## 1. 本次真正发现的系统缺陷

- **选题尺度缺失**：SC05 旧科学门控检验“机制可证伪”，但未区分论文审稿修补、局部子实验与可独立支撑新论文的城市系统级问题。R6.4.5 Gate-on 的溢出阈值、环线角色转换等有机制价值，但很容易把单城市内的某个局部实验误标为独立研究选题。
- **来源治理脱节**：用户之前批准的 A（Cities/SCS）、B（EPB/CEUS）、C（算法顶刊/顶会）目录保存在 Research Atlas 其他模块，但 SC05 使用泛化 OpenAlex 查询。R6.4.5 原始报告出现语言学/哲学/企业管理论文进入“最近科学先例”比较。
- **查新信号被混淆**：真实摘要引文、主题相似、同领域直接近邻、跨领域方法灵感、创新性证据被不同程度地混为一谈。
- **报告交付导向不足**：按多个诊断输出方案，却没有把“城市规划重要问题—新系统机制—治理决策—跨情境适用边界—整篇论文的研究章节”作为一体化交付标准。

## 2. A/B/C/D 期刊来源层级

以 config/sc05_source_catalog_v1.json 为版本化配置：

- **A：应用/实践**。Cities、Sustainable Cities and Society。
- **B：规划与城市计算前沿**。Environment and Planning B、Computers, Environment and Urban Systems。
- **C：经批准的计算机与空间AI方法**。NeurIPS、ICML、ICLR、AAAI、KDD、SIGSPATIAL、JMLR 等。C类只参与可迁移方法假说，不得成为规划研究“最近直接科学先例”。
- **D：领域直接竞争论文**。按照原论文领域分流至交通、规划/环境、水文、健康、住房专门刊物。这类证据弥补只看四本规划期刊造成的领域盲点，不自动扩充 A/B/C 监测名单。各领域需动态维护并人工批准新增来源。
- **Unlisted / Unverified**：可能是真实、有价值的工作，但未被批准进入正式近邻证据池；保存审核计数与ID，不让模型编造它不存在。审批加入目录后才用于正式证据。

**两阶段来源限制**：
1. 后端已有 ResearchSource 表及 openalex_source_id，SC05 在云端读取已启用且已解析的源ID，并在当前实验的共同证据快照里冻结。向 OpenAlex 发出对应 application(A)、theory(B)、method(C)、validation/counterexample(D) 请求时，若有匹配源ID，直接使用 primary_location.source.id 过滤。
2. 若尚无已解析ID，仅作一般检索，但从 OpenAlex 返回的 venue 字段中按**完整期刊名称或批准别名**过滤，不能让其它来源进入正式最近先例。无ID的检索必须显式标注 unfiltered_fallback，不可以假称已按期刊检索。

期刊资格和真实科学相关性是**两道独立门槛**。即便 A/B/D 已准入，仍需要摘要和直接机制关系查证，不能因为“是名刊”就声称研究新颖或相关。C类方法要有源/目标输入输出、机制不变性、否证实验、人工审核；不能把随机跨学科类比列为科学证据。

## 3. 面向独立论文的科学问题重构

保留已有论文事实抽取与数据—模型—指标链，也保留原论文瑕疵的独立审稿判断。但 scientific_value_triage 与 research_redesign 同时强化：

1. 从原研究**已发现的现象**出发，而不是从测量偏差或缺一个Bootstrap出发；
2. 明确城市规划现实重要性与目标决策主体；
3. 提出跨组件/行为/治理的系统机制及可竞争解释，不把一个站点的数值显著性包装为“城市规律”；
4. 明确新研究相较原研究的**尺度变化与适用边界**；
5. 给出可独立成篇的故事与多章节实验设计，而不是只提供补一个小检查；
6. 允许自主结论为“目前没有达到独立论文尺度的路线”并保留 HOLD，而不是强制生成三篇文章；
7. 不能把“跨城市/可泛化”作为凭空添加的事实，必须清楚说明数据与验证条件。

每条研究路线现在有 research_program 字段：
- contribution_level: robustness_fix / mechanism_substudy / independent_study / system_program；
- planning_problem、system_mechanism、planning_contribution；
- decision_stakeholders、generalization_boundary；
- paper_architecture、why_not_a_subexperiment。

以 backend/sc05_research_program.py 执行结构审计：所有字段齐备不意味着有新颖性；如果缺少 A/B 规划证据、可信直接近邻或独立批评为 hold/reject，绝不直接升级为“推荐新论文”。报告在正式正文展示项目尺度与分层证据，而不是仅在运行日志显示警告。

## 4. 完整流程与性能/预算边界

仍在原 Research Atlas SC05 **同一次科研工作流**执行：

source reading → verified facts → data/method dependency chain → diagnosis → science-frontier triage → A/B/C/D evidence questions & OpenAlex screening → literature and separate C-method bridge review → paper-scale route proposal → independent critic → quality/venue/program audit → final Markdown report → Owner archive.

- **没有增加付费模型调用阶段**；但 research_redesign 的输出结构更丰富，阶段 max_tokens 从4100提高至5400，新一次实验有可能消耗更多输出 tokens。此文档及PR不授权付费运行。
- 不修改既有 R6.4.5 提交、源SHA、盲评、云端报告、论文问答。
- 新目录/代码都纳入 SC05 pipeline_sha。后续两臂均使用冻结的来源ID快照，不能在 Gate-off/Gate-on 中途改期刊目录而制造比较偏差。
- 单次集成测试必须覆盖：A/B/C/D识别、无关哲学论文隔离、C方法不成为最近先例、自引剔除、正确 source_ids 提交、共享期刊快照冻结、完整模型模拟8阶段和科研报告中显式给出论文尺度审核、需要补充的规划证据。

## 5. 本次不能宣称的结果与下一步独立验收

这轮只能证明 **能力架构与程序化安全门槛** 实施。不能据此宣称模型真的提出了更重要的选题，或在真实未见论文上改进了发表机会。下一篇已发表、未用于调参/评价的论文需在明确付费授权后运行全流程，再由独立评审比较：
- 问题是否值得写独立论文，而不仅是某章/小实验；
- 学科贡献是否在 A/B 规划与城市科学问题中成立；
- 领域真实直接竞争工作是否覆盖且正确区分；
- C方法迁移是否真实可映射、具可证伪性，非纯口头类比；
- 是否有数据条件、替代方案、反对意见与可检验的整体研究架构。

**禁止按单独检索/选题模块发起付费微实验来代替整轮验收。** 任何测试失败应按同一集成版本修复，并在 PR 里留痕。
