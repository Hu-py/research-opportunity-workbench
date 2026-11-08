# Business Workspace Agent — 产品需求与目标架构 v1

> 状态：开发基线  
> 日期：2026-11-08  
> 主要入口：ChatGPT Business Workspace Agent  
> 长期数据源：Supabase PostgreSQL

## 1. 产品定位

**Research Opportunity Intelligence System（科研机会智能发现系统）**

系统的目标不是堆叠大量聊天 Agent，而是持续理解团队研究能力与资源，主动发现学术机会，通过证据检索、多视角假设生成、对抗性审查和有界修复，形成少量高质量、可验证、可执行的研究选题，并将团队最终评价积累为长期决策记忆。

## 2. 必须满足的用户需求

1. **团队级共享认知**：所有成员使用同一套数据库驱动的团队画像、研究主线、既有成果、数据资产目录、学术来源库和决策记录；不得把聊天历史或 ChatGPT Memory 当作科研事实来源。
2. **画像驱动发现**：研究机会必须从团队真实研究主线、方法积累、已登记数据属性和已有成果出发，不做无上下文的泛化选题。
3. **自动文献筛选**：初始论文检索和语义筛选由 LLM 完成，不要求人工先挑论文；保留相关性、贡献、证据角色、局限和置信度。
4. **多路径选题**：至少从科学问题、方法迁移、数据机会三个独立视角生成候选，不把“换模型名称”当作创新。
5. **多轮科研博弈**：候选必须经过独立评分、反向挑战、定向补充检索、反证审查和针对性修订；不得由初始生成 Agent 自己宣布成功。
6. **显式过程控制**：逐步实现 Task Contract → Multi-Agent Execution → Independent Task Evaluation → Repair Plan → Local Retry / Global Reroute。
7. **最终人工决策**：人工只在完整推荐包形成后介入。人工反馈必须由已登录团队成员提交，Agent 不得代填。
8. **可追溯与可复现**：保存上下文哈希、论文来源、证据 ID、候选版本、评分、反对意见、重试记录、预算和最终状态。
9. **持续改进**：将采纳、修改、暂缓、拒绝及其理由写入决策记忆，供后续 Agent 参考；现阶段不训练模型权重、不启用强化学习。
10. **中英文交付**：面向团队提供中文主体报告和英文题目/摘要，附可核验 DOI 或来源链接。

## 3. 当前阶段范围与明确排除项

### 当前开发范围

- 团队画像和数据资产上下文读取；
- 学术来源约束下的论文检索与 LLM 语义筛选；
- 三视角候选生成；
- 独立评价、对抗审查、反证检索和候选修订；
- 质量门槛、预算控制、运行状态和版本记录；
- 最终选题推荐与团队人工反馈。

### 当前不开发

- 自动执行真实科研实验；
- 自动运行任意用户代码或修改科研代码仓库；
- 自动训练用户模型；
- 强化学习、RLHF 或模型参数更新；
- 读取未授权的私有数据行、原始文件、个人信息或数据持有者信息。

推荐包可以给出最小实验方案、基线、指标和失败条件，但不得声称实验已经执行。

## 4. 最终架构与组件职责

| 组件 | 唯一职责 | 不负责什么 |
|---|---|---|
| ChatGPT Business Workspace Agent | 主交互入口、任务理解、研究总控、结果解释、报告交付 | 不作为数据库；不把对话记忆当作科研事实 |
| Render FastAPI + MCP | 安全工具网关、Python 科研执行、任务状态和预算控制 | 不作为长期数据存储 |
| Supabase PostgreSQL | 唯一持久化科研数据源 | 不负责科研判断 |
| Vercel | 后续看板、结果可视化和实验回放 | 不是 Business Agent 运行的前置条件 |
| Research Agent Lab | 独立架构试验、控制策略和评测基准 | 当前 V2 Dry-run 不作为生产科研执行引擎 |

**MCP 入口决策：**以当前 Render FastAPI 上的 OAuth-protected Streamable HTTP MCP 为唯一正式 Business 连接。暂不部署 Supabase Edge MCP 原型，避免两套工具、身份和写入规则并存。

**Render 决策：**Render 不是数据库必需品，但当前 Python 选题引擎和 MCP 服务已经部署在 Render。为了复用真实科研执行代码，现阶段保留 Render 作为轻量执行层。未来若迁移执行环境，只替换运行时，不迁移 Supabase 数据。

## 5. 端到端科研工作流

1. **Context Loading**：每次任务先读取授权的团队上下文和 context hash。
2. **Research Planning**：依据研究主线、已有成果、数据目录和历史决策规划检索方向。
3. **Literature Retrieval**：通过 OpenAlex 等已注册学术工具检索；来源注册表是检索优先级，不是唯一来源，也不是论文质量结论。
4. **LLM Paper Screening**：逐篇评估研究问题、贡献、证据角色、方法、局限和相关性。
5. **Independent Paper Referee**：独立复核初筛结果，补充最接近先前研究和相反证据。
6. **Multi-path Hypothesis Generation**：问题、方法、数据三个视角独立生成候选。
7. **Independent Hypothesis Judge**：评价科学价值、证据充分性、先前研究风险、可行性和可证伪性。
8. **Adversarial Challenge**：提出实质性反对意见和定向反证检索式。
9. **Counter-evidence Referee**：审查新增文献，判断先前研究风险。
10. **Targeted Revision**：根据具体缺陷修订，不允许只改标题或措辞。
11. **Final Quality Gate**：只有通过分数阈值、证据门控、可行性门控、可证伪性门控和先前研究审查的候选才进入推荐包。
12. **Persistence and Read-back**：写入数据库并重新读取确认；失败不得报告成功。
13. **Human Review**：团队成员对最终推荐作出采纳、修改、暂缓或拒绝，并记录理由。

程序可以拒绝无效 ID、无效 DOI、缺少字段、超预算或违反权限的结果；科学相关性、创新价值和方法贡献必须由 LLM 结合真实证据判断。

## 6. 现有生产引擎与待补能力

当前 Render 分支已有 `backend/research_evolution.py`、`backend/research_evolution_runner.py` 和 `backend/research_evolution_validation.py`。真实引擎已经包含：

- LLM 检索规划；
- 论文语义初筛和独立复核；
- 问题、方法、数据三个视角生成；
- 初始独立评分；
- 对抗性先前研究挑战；
- 定向反证检索与独立复核；
- 候选修订和最终评分；
- 最终推荐包、质量门槛、预算记录和人工反馈。

当前引擎是**单条研究主线、单次运行**：最多 14 篇论文、最多 10 次工具调用、三个独立初始候选视角，最终质量分阈值为 80。它尚未完整实现正式的 Task Contract、独立 Task Evaluator、结构化 Repair Plan 和 Meta Supervisor 全局路由。后续应将 Research Agent Lab V2 中经过验证的控制思想迁移到生产引擎，但只迁移选题相关阶段，不迁移实验执行阶段。

Research Agent Lab 的 V2 当前默认使用合成数据 Dry-run，只能作为控制架构试验基准，不能把模拟结果称为真实科研发现。

## 7. Business MCP 工具契约

### 数据读取

- `get_research_context`：读取授权团队画像、成果、公开数据资产元信息、论文和人工决策历史，并返回 context hash。
- `get_run_history`：读取 Business Agent 直接提交的历史推荐。
- `get_research_run`：读取一份已保存的 Business Agent 推荐及其持久化 ID。

### 科研执行

- `check_topic_advisor_readiness`：检查指定研究主线、模型密钥和预算是否满足启动条件。
- `start_topic_advisor`：启动一条研究主线的真实多 Agent 选题任务，返回持久化 run ID。
- `get_topic_advisor_run`：读取运行状态、论文筛选、候选版本、评分和最终推荐。
- `list_topic_advisor_runs`：查看最近运行记录。
- `resume_topic_advisor_run`：从最后一个持久化阶段恢复失败或已停滞任务。

### 写入

- `submit_research_run`：保存 Workspace Agent 直接完成、且未由选题引擎重复保存的证据关联推荐。
- **不提供** `save_human_feedback` MCP 工具。人工反馈必须走团队登录后的成员 API。

### 权限分层

- `research:read`：读取授权上下文和运行结果；
- `research:execute`：启动/恢复会消耗模型和检索预算的科研任务；
- `research:write`：提交直接推荐结果。

三个权限由服务器端用户 ID、OAuth client ID 白名单和独立开关控制，不能相信 JWT 中任意自报的 scope。首次连接只开放读取；完成授权测试后，再分别开放执行和写入。

## 8. 模型分工与运行预算

- Workspace Agent 本身使用 ChatGPT Business 工作空间中选择的模型，承担交互、任务理解、上下文解释和结果交付。
- 当前后端多 Agent 选题引擎使用已配置在 Render/Supabase-backed Model Vault 中的 DeepSeek API。ChatGPT Business 席位不等于后端 OpenAI API 额度。
- 若以后希望内部多 Agent 也全部使用 OpenAI API，需要单独评估 API 费用、密钥和执行方案；不把 Workspace Agent API Trigger 当作内部 Agent 间通信总线，因为其 API 当前不能返回 Agent 最终回答。

目标运营规模（通过试运行后逐步启用）：

- 每轮最多 5 个研究主题；
- 每日最多分析 80 篇论文；
- 每日文献预分析；
- 每周综合研究机会报告。

首轮只运行 1 条研究主线、最多 14 篇论文。当前执行工具一次只启动一条研究主线；批量 5 主题调度属于后续开发，不得把目标规模误报为当前已实现能力。

## 9. 发布阶段与验收标准

### P0 — Business 接入准备

- [x] Supabase 为唯一长期数据库；
- [x] Render 上有独立 OAuth consent 页面代码；
- [x] Render 上有默认关闭的 OAuth MCP adapter；
- [x] 有 Business Agent 持久化记录和证据校验；
- [ ] Business MCP 工具扩展为可检查、启动、读取和恢复科研任务；
- [ ] CI 通过。

### P1 — 私有只读连接

- ChatGPT Business 成功完成 OAuth PKCE；
- 未授权用户和 client 均返回 401/403；
- 读取上下文不包含受限数据和原始文件；
- 每次新会话均从 Supabase 读取真实上下文。

### P2 — 单主线真实运行

- 单次运行可以由 Workspace Agent 启动；
- Agent 能读取状态、论文、候选版本和最终推荐；
- 预算耗尽或执行失败时能如实报告；
- Render 重启后数据库中仍有完整运行记录；
- 只有独立质量门槛通过的候选才进入最终推荐。

### P3 — 科研质量控制升级

- 为每个阶段建立 Task Contract；
- 独立 Evaluator 判断任务是否真正解决缺陷；
- Repair Plan 明确要修复的问题、证据和目标阶段；
- Meta Supervisor 选择局部重试或全局回退；
- 保留中间版本、评价理由和路由记录。

### P4 — 批量和定时运行

- 支持最多 5 个主题的顺序调度；
- 全局每日 80 篇论文硬预算；
- 通过试运行后再启用 Workspace Agent 每日/每周 Schedule；
- 周报从已持久化的运行结果生成。

### P5 — 决策记忆完善

- 将最终人工反馈与历史候选、研究主线关联；
- 归纳团队在问题重要性、创新性、方法和可行性上的稳定判断；
- 先使用可审计的决策记忆，不进行自动模型训练或强化学习。

## 10. 当前发布安全边界

- Render 当前服务使用 `feat/shared-team-workspace` 分支，且自动部署关闭；本轮开发从该运行分支建立独立 feature branch，CI 通过后再合并和手动部署。
- 不把与运行分支严重分叉的 `main` 整体合并进当前服务。
- `BUSINESS_MCP_ENABLED`、`BUSINESS_MCP_WRITE_ENABLED`、`BUSINESS_MCP_EXECUTION_ENABLED` 默认关闭。
- 不把 Supabase Secret/Service Role Key、数据库 URL、DeepSeek Key 或 OAuth Token 写入 GitHub、Agent Skill 或提示词。
- Workspace Agent 的创建、连接和团队分享必须在 ChatGPT Business 管理界面完成；代码仓库不能代替该 UI 操作。


## 11. Execution reliability boundary

The first MCP execution implementation returns a persistent run ID and starts the current Python pipeline as an in-process background task on Render. The pipeline checkpoints its stage outputs and trace to Supabase after each completed stage. If Render restarts or the process is interrupted, the run record remains in Supabase and can be resumed after the existing eight-minute stale-run guard.

This is sufficient for a controlled single-line pilot, but it is **not yet a durable distributed job queue**. The current engine also permits only one active evolution run globally. Before enabling five-theme batches, 80-paper/day automation or unattended daily schedules, add a durable queue/worker design (for example Supabase Queues plus a separately managed worker, or an equivalent persistent execution service), idempotent job claims, heartbeat/lease expiry and bounded retry policy.
