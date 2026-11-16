# Research Atlas｜统一架构实施总表 V1.0

> **审计基准日：2026-11-16**  
> **维护分支：** `chore/repo-governance-sc05-chatgpt-20261116`  
> **适用范围：** Research Atlas 产品、科研 Agent、科研发现与知识资产、Development Studio、SC05 实验执行、身份权限、数据与部署基础设施。  
> **本文件定位：** 统一实施台账，不是新的架构设想。以 GitHub 代码、PR/CI、Vercel 部署记录、Render 部署审计和已验证的运行证据为依据。  
> **重要边界：** 本文件当前位于 Draft PR #98 的整理分支；尚未合并到 `main`，也没有因为写入文档而触发任何 Render 或 Vercel 部署。

---

## 0. 一页结论

Research Atlas 已经形成可复用的前端、后端、科研 Agent、数据模型和云端实验执行基础，但目前处于**生产主线 + 隔离测试线 + 新功能 Draft 分支并存**的阶段，不能把所有仓库代码视为已经上线的统一产品。

| 维度 | 当前判断 | 关键证据 / 限制 |
|---|---|---|
| 产品前端 | V0.5 主界面已部署 | Vercel 生产部署 READY；首页仍以批准版静态 HTML 为入口，不代表全部业务模块已接通 |
| 核心后端 | FastAPI、Next.js 代理、基础数据库和通用任务能力已存在 | 生产与隔离测试服务必须分开核验 |
| 科研 Agent | 原有 Research Agent、Skills、Radar 和研究资产能力已存在 | 新版三来源科研发现、统一 Skill 调用仍有 Draft 工作 |
| Development Studio | 隔离测试分支已有实验登记、版本和审计实现 | 不等于已合并或发布到生产主线 |
| SC05 实验引擎 | 论文理解、证据重建、诊断、Scientific Value Gate、A/B Run 和检查点已有隔离环境实现 | 真实科研质量仍需完整 A/B、盲评和跨论文验证 |
| ChatGPT MCP | 最新代码分支已设计完整 A/B 工作流工具 | 当前整理分支尚未部署到 Render；当前 ChatGPT 会话实际暴露的工具清单仍少于代码注册清单 |
| 云端执行 | 已有 PostgreSQL 队列和 Render inline worker 实现 | 免费 Web Service 可能休眠或重启；不能等同于常驻高可用 Worker |
| 持久化 | PostgreSQL 是权威数据源；R2 归档适配器已实现 | R2 在线归档未完成端到端确认；隔离免费数据库有到期风险 |
| 团队权限 | 成员、角色、会话和审计基础代码存在 | Owner 邀请/邮箱验证及生产启用仍需验收 |
| 生产整合 | 尚未完成 | 生产 main、隔离 staging、PR98 整理分支的版本边界仍需保持清晰 |

**当前工程主目标：** 先在 ChatGPT 中真正完成一组可追溯的 SC05 A/B 科研工作流评测，再以同一套身份、数据和版本治理方式逐步整合其他科研能力。SC05 是当前最完整的端到端验收样板，不代表 Research Atlas 的全部科研模块都已完成。

---

## 1. 状态口径：必须分开记录四种“完成”

| 状态维度 | 状态值 | 定义 | 不能据此声称 |
|---|---|---|---|
| 代码 | `CODE-MAIN` | 已进入默认分支 `main` | 不代表生产环境已运行该版本 |
| 代码 | `CODE-STAGING` | 已进入隔离测试分支 | 不代表已部署或已通过真实用户验收 |
| 代码 | `CODE-DRAFT` | 仅存在于未合并 PR / 功能分支 | 不代表当前服务可调用 |
| 测试 | `TEST-CI` | 对应 commit 的 CI / 自动化测试通过 | 不代表真实外部服务或模型调用成功 |
| 部署 | `DEPLOY-PROD` | 已核对生产环境实际运行 commit | 不代表所有功能质量通过 |
| 部署 | `DEPLOY-STAGING` | 已核对隔离服务实际运行 commit | 不代表可以用于生产数据 |
| 验收 | `ACCEPT-E2E` | 真实用户链路按验收标准完成 | 不代表科研结论自动正确 |
| 验收 | `ACCEPT-SCIENCE` | 证据、科学价值、独立性和泛化均经过评价 | 不由 CI、部署或单次成功运行替代 |
| 阻塞 | `BLOCKED` | 有明确依赖、权限、费用、环境或数据阻塞 | 不得标为已完成 |

### 状态标记原则

1. 每个模块至少分别填写代码状态、测试状态、部署状态、业务验收状态。
2. 没有证据时写“未核验”，不根据文件存在或历史聊天推断。
3. Draft PR、隔离分支、Preview 和生产主线必须分开。
4. 真实模型调用必须记录模型、调用量、token、费用/预算、来源哈希、pipeline 哈希和检查点。
5. 科研质量评价与平台技术验收分开，不得用一个“完成”状态覆盖。

---

## 2. 统一架构拓扑

```text
Researcher / Team Member
        |
        +-----------------------------+
        |                             |
        v                             v
ChatGPT + OAuth / MCP           Browser + Vercel Next.js
        |                             |
        | /mcp                        | HttpOnly session
        |                             | same-origin API proxy
        +--------------+--------------+
                       |
                       v
                Render FastAPI
                 backend/api.py
                       |
       +---------------+--------------------+
       |               |                    |
       v               v                    v
  Research Agent   Development Studio   SC05 Owner API
  Radar / Skills   Experiment Registry   Paper / A-B / Audit
       |               |                    |
       +---------------+--------------------+
                       |
                       v
                   PostgreSQL
        Users / Papers / Evidence / Tasks /
        Experiments / Runs / Checkpoints /
        Budget / Audit / Experiment Rounds
                       |
             +---------+----------+
             |                    |
             v                    v
      Render execution       Cloudflare R2
      general worker /       optional private
      SC05 inline worker     archive and backup
             |
             v
       Model Gateway / Vault
       DeepSeek / other LLM APIs

GitHub:
source code / Skills / PR / CI / workflows / release evidence

Separate Vercel project:
dev-tracker (engineering Issue / PR / Commit / CI tracking)
```

### 两条用户入口，不是两套数据系统

- **ChatGPT → Render MCP：** 通过 OAuth Authorization Code + PKCE 取得 Owner 授权，调用范围受限的 SC05 工具。
- **Browser → Vercel → Render：** 浏览器使用 Next.js 服务端代理访问 FastAPI，不直接持有后端 Bearer Token、模型密钥、数据库凭据或 R2 密钥。
- 两条入口应共用 PostgreSQL 中的 Owner、论文、实验、运行和审计记录；不得分别维护两套互不关联的实验状态。

---

## 3. 统一架构实施总表

> 表中“当前实现”描述代码和已知运行证据；“部署/验收”描述是否已进入目标环境。P0 表示当前阻塞整体闭环的工作，P1 表示核心整合，P2 表示后续能力建设。

| ID | 层级 / 模块 | 当前代码与主要位置 | 当前实现状态 | 测试 / 部署证据 | 尚未打通 / 下一步验收 | 优先级 |
|---|---|---|---|---|---|---|
| UI-01 | Research Atlas 主前端 | `frontend/app/page.tsx`、`frontend/public/research-atlas-v0.5.html`；PR #59–61 | V0.5 黑白极简入口已实现 | main 生产 Vercel 最新记录为 READY，commit `71950ac4`；首页重定向到批准版 HTML | 逐项核验页面上的真实业务交互；静态展示不能当作 AI 对话或持久化功能 | P1 |
| UI-02 | 对话与会话体验 | `frontend/components/AtlasConversation.tsx`、`frontend/lib/session.ts` 等 | 有界面与会话基础组件 | V0.5 主入口当前仍是静态 HTML；PR #60 明确指出持久化多轮聊天和私人/团队 ACL 尚未完整实现 | 完成多轮消息持久化、会话列表、上下文恢复、私人/团队聊天隔离、对话转任务 | P0 |
| UI-03 | Browser API 代理 | `frontend/app/api/proxy/[...segments]/route.ts`、`frontend/lib/api.ts` | Next.js 服务端代理和会话路径已存在 | main 代码存在；生产变量与当前后端目标需逐环境核验 | 验证登录、会话续期、401/403、文件上传、错误透传；确认绝不向浏览器暴露服务端密钥 | P1 |
| API-01 | FastAPI 主后端 | `backend/api.py`、`backend/repository.py` | 已有主 API、研究任务、论文、画像和功能路由 | main 已有代码；Render 具体生产 API commit 不在本表中冒充已核验 | 统一路由注册、版本化 API、健康检查、权限和异常响应；明确生产/测试后端 | P1 |
| GOV-01 | 团队身份与角色 | `backend/team.py`、`frontend/lib/session.ts`、`docs/TEAM_SETUP.md` | 成员、角色、会话、审计和权限基础代码存在 | 历史部署文档显示团队登录仍需完成首个管理员初始化与开关核验；PR #65 邀请/开通能力仍为 Draft | 完成真实 Owner 初始化、Admin/Researcher/Viewer 权限矩阵、邀请/撤销/恢复、审计和真实邮箱验证 | P0 |
| UI-04 | Development Studio 页面 | `frontend/app/devstudio/route.ts`、`frontend/lib/devstudio-approved-html.ts`、`frontend/lib/devstudio-live-bridge.ts` | 隔离分支已实现批准版页面和真实交互桥 | PR #63 仍为 Draft；PR #64 是隔离 E2E；不能视为 main 生产已发布 | 完成七个模块的真实浏览器验收、权限验收、空数据/错误态验收，再单独审议生产发布 | P0 |
| EXP-01 | Development Studio 实验登记 | `backend/devstudio.py`、`backend/experiment_management.py`、`frontend/app/devstudio/experiments/` | V0.4 分类、revision、状态门禁、事件历史、运行关联和人工评价已在隔离线实现 | PR #67 已合并到隔离 E2E 分支；PR #68 补录研发历史快照 | 生产发布前核验持久化、并发编辑、Viewer 禁写、审计事件；不能把“有评价记录”视为科研成功 | P1 |
| OPS-01 | 独立研发追踪器 | `dev-tracker/` | 独立 Issue / PR / Commit / CI 追踪项目 | 仓库 README 指向独立 Vercel 项目 `research-atlas-dev-tracker`；本轮未重新核验其最新线上 commit | 核验刷新、权限、PR/CI 事件同步和限额；避免与 Development Studio 实验台账重复记账 | P2 |
| AG-01 | 基础 Research Agent | `backend/agent.py`、`backend/scientific_agent.py`、`backend/scientific_tools.py` | 有基础 Agent、白名单工具和研究能力模块 | main 有对应代码；不是全部新版科研工作流已统一接入 | 建立统一 Agent runtime / tool registry / run context；定义不同 Agent 的输入、输出、权限和版本 | P1 |
| AG-02 | Skills 与科研方法 | `skills/`、`backend/skill_loader.py` | 论文阅读、方法迁移、Idea Critic 等 Skill 已存在 | main 有版本化 Skill；SC05 的 `research_diagnosis` 在隔离线 | 统一 Skill 版本、依赖、调用记录和评测；把已确认的 GPT 能力迁入可复用服务，而非复制提示词 | P1 |
| RAD-01 | Research Radar / 文献发现 | `backend/discovery.py`、`backend/research_sources.py`、`backend/radar_pipeline.py`、`.github/workflows/` | OpenAlex 采集、Radar A/B、来源目录和周报流程已有实现 | main 有定时/手动工作流；具体 DB 周报运行仍需独立验收 | 核验数据新鲜度、来源覆盖、周报数据库依赖；完成新三来源科学发现流程的证据验收 | P1 |
| RAD-02 | 三来源科研智能发现 | PR #57；`feature/atlas-three-source-ai-workflow-v01` | A/B/C 来源计划、证据校验、L0/L1 proposal 已有 Draft 实现 | PR #57 Draft，尚未并入 main；未完成六个固定任务的真实证据验收 | 完成真实来源检索、论文覆盖、负例/近邻、人工审查，再接入正式任务调度和前端 | P1 |
| DATA-01 | 论文库与研究证据 | `backend/repository.py`、`backend/research_evidence_export.py`、`backend/cusp.py` | 论文、Idea、Evidence、画像和数据资产有既有数据模型 | main 有存储和读取路径；不同模块证据引用尚未统一 | 统一 Paper ID、Evidence ID、来源 URL/DOI、页码、版本和证据等级；实现跨模块可追溯关联 | P1 |
| DATA-02 | 研究画像与团队资产 | `backend/profile_database.py`、`backend/profile_intelligence.py`、`backend/interests.py` | 团队画像、研究兴趣和资产目录能力存在 | main 有对应模块；个人画像与正式团队画像必须保持边界 | 统一团队事实、个人偏好、研究兴趣、已验证能力和 provisional 信息的权限与来源标记 | P2 |
| DATA-03 | 跨论文知识图谱 / 长期知识记忆 | 现有 Evidence / Paper / Profile 可作为基础 | 尚未形成统一、经验证的跨论文知识图谱与知识更新机制 | 不能把已有论文库或局部 evidence ledger 说成完整知识图谱 | 定义抽象知识实体、关系、来源回链、冲突/反例、版本和人工确认机制 | P2 |
| MODEL-01 | 模型网关、密钥和预算 | `backend/model_gateway.py`、`backend/model_vault.py`、`backend/research_budget.py` | 模型调用、加密凭据和预算记录基础已存在 | SC05 隔离线有真实 DeepSeek 调用历史；不同流程的模型配置仍需核验 | 统一 provider/model 配置、超时、限流、token/费用计量、重试政策和日志脱敏；模型密钥只留服务端 | P1 |
| TASK-01 | 通用科研任务与 Worker | `backend/tasks.py`、`backend/worker.py` | 数据库任务、步骤和结果持久化以及 Worker 代码存在 | main 有通用任务执行路径；架构文档记录崩溃恢复、取消、重试/死信仍有限 | 补充 heartbeat、lease、stale-job 管理、取消/恢复、重试上限和死信处理 | P1 |
| SC04-01 | 个人研究演化 | `backend/sc04_evolution.py`、相关 API / runner；PR #76 | 个人研究演化试点已在隔离分支开发 | PR #76 已合并到隔离 E2E 线；不是 main 生产能力 | 明确与团队级 Research Evolution 的边界，完成真实用户隔离、基线确认、论文来源和质量验收 | P2 |
| SC05-01 | 论文理解与证据重建 | `backend/sc05_paper_only.py`、`backend/sc05_research_diagnosis.py`、Skill；PR #83 | 单篇论文输入、页面证据、方法/结果重建、诊断和报告已实现于隔离线 | PR #83 已合并到隔离 E2E 线；有真实模型调用历史和失败修复记录 | 对每个事实保持原文页码/片段回链；验证不能把模型推断当作论文事实 | P0 |
| SC05-02 | Scientific Value Gate 与研究问题形成 | `backend/sc05_science_gate.py`；PR #84 | 把科学价值 triage 与方法/研究设计审计分开，强调现象、机制、研究问题和可区分实验 | PR #84 已合并到隔离 E2E 线；真实质量结论仍需盲评 | 验证能否独立形成非平凡研究问题，而不只是指出原论文局限或建议增加敏感性分析 | P0 |
| SC05-03 | A/B 运行引擎 | `backend/sc05_eval_api.py`、`backend/sc05_replay.py`、`backend/research_budget.py`；PR #85、#87、#93、#94 | A/B Run、共同证据冻结、pipeline/source 指纹、阶段检查点、预算、恢复检查和盲评接口已有隔离实现 | PR #85 等已合并至隔离分支；历史运行有真实 DeepSeek 调用，但不能据此宣布本轮科研质量通过 | 新轮次必须创建干净配对；先完成 baseline 再 treatment；严格检查来源哈希、pipeline SHA 和旧检查点 | P0 |
| SC05-04 | ChatGPT MCP / OAuth | `backend/sc05_agent_bridge.py`；PR #95–#97、#98 | Owner OAuth/PKCE、read/run scopes、零成本创建、A/B 编排、盲评和轮次工具已在 PR #98 代码中扩展 | PR #95–#97 已合并到隔离 E2E 线；PR #98 Draft 的 CI 和隔离安全 smoke 已通过；PR #98 尚未部署 | Render 手动部署 PR #98 对应 commit；Owner 重新授权；ChatGPT `tools/list` 必须核对 16 项工具；当前对话实际只暴露旧的 6 项工具 | P0 |
| SC05-05 | A/B 配对级工具 | PR #98；`backend/sc05_agent_bridge.py` | 代码清单包含 `create_paper_case`、`create_ab_pair`、`prepare_ab_pair`、`get_ab_pair_status`、`start_ab_pair`、`get_ab_pair_result`、`record_blind_review`、`compare_ab_pair` | PR #98 自动化测试覆盖工具注册、scope、零成本建档、配对隐私；当前部署尚未更新 | 部署后在 ChatGPT 验证创建论文案例、A/B 配对、预检、顺序启动、匿名结果、盲评和解盲；不允许绕过授权 | P0 |
| SC05-06 | 实验轮次台账 | PR #98；`SC05ExperimentRound`、`list_experiment_rounds`、`record_experiment_round` | 轮次表设计已进入 PR #98，记录类别、问题、方法、实验内容、状态、简要结果、后续、详细记录和 pair/source/pipeline 关联 | CI 测试已覆盖轮次写入逻辑；尚未部署到当前 Render Live commit | 部署后验证 PostgreSQL 持久化、刷新后读取、更新历史、A/B 状态同步和详细记录完整性 | P0 |
| SC05-07 | 盲评与解盲 | `record_blind_review`、`compare_ab_pair`；PR #98 | 设计为两份匿名报告分别评分，评分齐全后才解盲；A/B 映射在解盲前隐藏 | PR #98 有测试覆盖盲映射隐私；未完成真实评测员流程验收 | 验证评分顺序、身份暴露边界、硬失败处理、加权比较和审计记录；不能把助手自评称为独立外部盲评 | P0 |
| RUN-01 | SC05 云端执行器 | `backend/sc05_worker.py`；PR #97 | 使用现有 Render Web Service 的 inline worker 消费 Owner 明确授权的 dispatch；不自动重放历史失败任务 | PR #97 已合并至隔离 E2E 线；PR #98 未重新部署；免费实例可能休眠/重启 | 核对 live commit、零成本 PostgreSQL probe、执行器状态、队列消费者和 readiness flags；再由用户单独授权有限真实调用 | P0 |
| DB-01 | PostgreSQL 持久化 | `research_workbench/core.py`、SQLAlchemy 模型和 Render PostgreSQL | PostgreSQL 作为论文、用户、任务、实验、检查点、审计和轮次台账的 source of truth | 隔离 E2E 数据库已建立；历史审计记录其免费实例计划到期日为 2026-12-04 | 立即核验到期时间、导出、备份和恢复；明确长期数据库；禁止把测试数据无审查迁入生产 | P0 |
| STO-01 | Cloudflare R2 归档 | `backend/r2_storage.py`、`backend/sc05_r2_artifacts.py`；PR #91 | 私有归档适配器和 SC05 source/checkpoint/report manifest 逻辑已实现 | PR #91 合并到隔离分支；历史 GitHub Actions R2 roundtrip 成功，但 Render 侧 R2 凭据和完整 artifact audit 未确认 | R2 保持可选；验证 bucket 权限、source SHA、checkpoint SHA、manifest、report/result；R2 故障不得触发重复模型调用 | P1 |
| OPS-01 | GitHub CI / 自动化 | `.github/workflows/ci.yml`、Radar / weekly workflows | Python、前端构建、兼容 smoke、数据采集和同步工作流存在 | PR #98 head commit `223abf189b5450581c164ff138caa3e14ed0b0a9` 的 GitHub CI 和 SC05 isolated security smoke 已通过 | 保持 CI 与真实部署、真实模型、科研质量验收分层；记录每次 release 对应的精确 commit | P1 |
| OPS-02 | Vercel / Render 发布 | Vercel 主项目、Render 隔离 E2E 服务 | 生产前端和隔离 API 分别存在 | Vercel main 生产部署 READY；Render staging 自动部署关闭，已知 Live commit 为 `262f3b053bb8a3910aed85bda1665073fcfad5f1`；PR #98 commit 未部署 | PR #98 Preview 曾因 Vercel 免费每日部署限额失败；Render 需人工部署；每次部署后核对 live commit 和 /health | P0 |
| GOV-02 | 分支、版本和发布治理 | `docs/BRANCH_LIFECYCLE.md`、PR 模板、文件清单 | PR #98 已加入分支生命周期、文件用途分类和 PR 验收模板 | PR #98 Draft；文档与治理代码尚未合并 | 保持 main / staging / feature / experiment 分工；禁止把 staging 合并当作生产发布 | P1 |
| FUT-01 | 多人科研协作与知识沉淀 | 团队权限、Profile、Paper、Evidence、任务和聊天基础 | 共享画像、共享论文资产和角色基础已有；私人/团队对话 ACL、长期个人画像和统一知识图谱未完成 | 相关需求已有 PRD / 代码片段，但没有全链路验收 | 在稳定的身份与数据模型上，分阶段建设私人/团队对话、用户画像、跨论文知识图谱和可追溯知识更新 | P2 |

---

## 4. 关键接口连接矩阵

| 起点 | 终点 | 接口 / 数据 | 当前状态 | 主要断点 / 验收 |
|---|---|---|---|---|
| ChatGPT | Render FastAPI | OAuth 2.1 / PKCE → `/mcp` | 代码已实现于隔离线；PR #98 未部署 | 重新授权后核对 MCP discovery、tools/list、read/run scope |
| Browser | Vercel | Next.js 页面、HttpOnly session | 生产前端已部署 | 静态 V0.5 与真实业务路由需逐页核验 |
| Vercel | Render FastAPI | 同源 `/api/proxy`、服务端 Bearer | 基础代理存在 | 核对生产与 Preview 指向的后端、会话和权限 |
| Render API | PostgreSQL | SQLAlchemy / DATABASE_URL | 隔离数据库存在 | 备份、到期和长期持久化策略未最终验收 |
| SC05 MCP | SC05 REST | Owner 范围的 case/pair/run 操作 | PR #98 代码覆盖完整 A/B 操作 | 当前 ChatGPT 工具清单未刷新到最新 16 项 |
| Render inline worker | PostgreSQL queue | 授权 dispatch、claim、checkpoint | PR #97 已合并到隔离线 | 核验当前 live commit 和无模型 probe；中断任务人工检查 |
| Render Worker / API | DeepSeek | 服务端模型凭据、预算和调用 | 隔离线有真实调用历史 | 需每次显式授权；验证 provider response、token 和 checkpoint |
| PostgreSQL | Cloudflare R2 | 私有 source/checkpoint/report archive | 可选适配器已实现 | Render 侧凭据与完整归档尚未验收 |
| Development Studio | SC05 | pair/run/status/evaluation linkage | 部分状态同步和实验关联已有代码 | 统一轮次记录与开发实验 registry 的关联仍需端到端核验 |
| GitHub | Vercel / Render | PR、CI、部署 | Vercel 主线自动部署；Render staging 手动部署 | GitHub merge 不等于 Render 已更新；Preview 有免费部署限额 |

---

## 5. 当前发布线与环境边界

| 环境 / 分支 | 当前定位 | 已知版本 / 状态 | 可以做什么 | 不允许混淆的事项 |
|---|---|---|---|---|
| GitHub `main` | 默认生产主线 | Vercel 生产记录 READY，commit `71950ac4c521350aa1113c4ba209252d456117fa` | 生产前端与 main 已发布能力 | 不包含所有 SC05 / DevStudio 隔离分支的新功能 |
| Render `experiment/devstudio-postgres-e2e-20261114` | 隔离 E2E / SC05 staging | 历史部署审计：Live commit `262f3b053bb8a3910aed85bda1665073fcfad5f1`；`autoDeploy=no` | 验证 Owner、DevStudio、SC05、MCP 和 PostgreSQL | 不是生产 API；不能指向生产数据库 |
| 整理分支 `chore/repo-governance-sc05-chatgpt-20261116` | 当前架构治理与完整 ChatGPT A/B 功能整理 | PR #98 Draft；head `223abf189b5450581c164ff138caa3e14ed0b0a9`；CI / isolated security smoke passed | 审查文件清单、MCP 完整工作流、操作指南和架构文档 | 尚未部署到 Render；Vercel Preview 因免费每日部署限额未成功 |
| Vercel `research-atlas-dev-tracker` | 独立工程追踪器 | 独立项目存在；本轮未核验最新部署 commit | 跟踪 Issue / PR / Commit / CI | 不等同于 Research Atlas 主应用内的 Development Studio |
| Cloudflare R2 | 可选私有归档 | 适配器存在；Render 端到端归档未确认 | 保存来源页、检查点和报告副本 | PostgreSQL 仍是权威状态；不能把 R2 roundtrip 等同于完整业务归档 |

**部署纪律：** Render staging 的自动部署为关闭。任何 staging PR 合并后，必须显式部署并核对 live commit；Vercel Preview 构建失败不能被解释为 GitHub CI 失败，也不能被解释为 Render 已部署。

---

## 6. 下一阶段实施顺序与完成定义

| 顺序 | 里程碑 | 具体工作 | 完成定义 | 阻塞解除后进入 |
|---|---|---|---|---|
| M0 | 锁定版本与数据安全 | 确认 staging 分支、Render Live commit、PostgreSQL 备份/到期和数据隔离 | 有精确 commit、数据库备份和回滚记录 | M1 |
| M1 | 合并并部署 PR #98 到 staging | 审查 PR #98；合并到 E2E staging；手动 Render deploy | Render Live commit 与目标 commit 一致，/api/health 正常 | M2 |
| M2 | 刷新 ChatGPT MCP 工具 | Owner OAuth 重新授权 read/run；检查 tools/list | ChatGPT 实际显示 16 项当前工具，scope 与写操作符合预期 | M3 |
| M3 | 零成本完整链路 | 创建 paper case、创建 A/B pair、登记 round、pair preflight、读取 status/result 接口 | PostgreSQL 中持久化 case/pair/round；无模型调用、无费用；刷新后仍可读取 | M4 |
| M4 | 执行器就绪检查 | 检查 worker probe、queue、budget、checkpoint、R2 开关 | 无模型 probe 完成；执行器 readiness 通过；没有历史任务被误消费 | M5 |
| M5 | 一组真实 A/B | 用户单独明确授权；先 baseline，后 treatment；读取匿名结果、盲评、解盲比较 | 两组真实结果、source/pipeline SHA、token、checkpoint、评分、比较和轮次记录全部可追溯 | M6 |
| M6 | 科研质量与泛化验收 | 评估科学价值、证据质量、机制叙事和可行性；再用未见论文验证 | 同一论文回归 + 至少一篇 held-out 论文；负面结果和失败归因保留 | M7 |
| M7 | 生产整合审议 | 将经过 staging 验收的功能拆分 PR 合入 main；完成权限、备份、回滚和安全审查 | 生产部署、真实 Owner/成员权限、恢复演练和端到端验收通过 | 后续 V0.6 |

### M0–M5 的执行边界

- 创建论文案例、创建 A/B 配对、预检、读取状态和登记轮次应为零模型调用。
- 只有真实模型运行才消耗 DeepSeek 预算，必须有当前用户明确授权。
- A/B 必须先运行 baseline，再在共同冻结证据上运行 treatment。
- 失败任务先检查状态、来源哈希、pipeline 哈希和检查点；不得静默重放或自动重试不确定的付费阶段。
- 两份报告完成并盲评后才允许解盲。
- 同一篇论文上的提升只证明 benchmark-specific improvement，不能直接声称跨论文泛化。

---

## 7. 当前 P0 阻塞清单

| 阻塞 ID | 问题 | 影响 | 解除条件 |
|---|---|---|---|
| B-01 | PR #98 尚未合并/部署到 Render staging | 最新 A/B 工具代码无法成为当前线上服务能力 | 审查并合并到隔离分支，手动部署并核对 live commit |
| B-02 | ChatGPT 当前 MCP 工具清单未同步最新代码 | ChatGPT 无法直接调用最新 pair-level / round-level 工具 | Owner 重新授权，实际 tools/list 核验 16 项工具 |
| B-03 | Render inline worker 与零成本 probe 需要部署后核验 | 无法仅凭代码或日志断言队列已可安全运行 | 读取执行器状态、probe completed、queue readiness |
| B-04 | 隔离 PostgreSQL 免费实例存在到期风险 | 可能影响实验历史、检查点和轮次台账长期保存 | 备份、恢复验证并确定长期数据库 |
| B-05 | R2 Render 归档未完成端到端验收 | 数据库以外的私有归档保障不足 | 上传/读取/哈希/manifest/report 全链路验证 |
| B-06 | Vercel Preview 受免费每日部署限额阻塞 | 无法通过本次 Preview 验证 PR #98 的前端构建产物 | 限额恢复后重新部署 Preview；不能用 GitHub CI 替代浏览器验收 |
| B-07 | 生产 main 与 staging 功能差距较大 | 用户可能把“代码已写”误认为“正式网站已可用” | 先 staging 验收，再分 PR 审议生产发布 |

---

## 8. 统一维护规则

1. **本表是架构实施状态的总索引。** 各模块的详细设计、API、操作和实验原则继续放在各自专题文档中，本表不复制全部技术细节。
2. 每个模块只维护一个主状态记录；同一事实不要在多个独立表格中手工维护互相冲突的状态。
3. 状态变化必须附证据：PR/commit、CI URL、部署 ID/Live commit、API 回读、日志、数据库核验或人工验收记录。
4. 每次变更记录：变更前状态、变更内容、原因、影响模块、验证方式、结果、回滚方式。
5. **代码合并 ≠ 部署；部署成功 ≠ 业务验收；业务验收 ≠ 科研质量通过。**
6. 历史失败、旧 Run、旧 checkpoint 和负面结果不得删除或覆盖。
7. Render / Vercel / PostgreSQL / R2 的密钥、Token、密码和数据库 URL 不进入文档或 Git。
8. 本表更新时同步核对 [仓库总览](REPOSITORY_MAP.md)、[文件使用状态清单](REPOSITORY_FILE_INVENTORY.md)、[分支生命周期](BRANCH_LIFECYCLE.md) 和 [SC05 操作指南](SC05_CHATGPT_OPERATING_GUIDE.md)。

---

## 9. 相关文档

- [仓库总览与系统边界](REPOSITORY_MAP.md)
- [文件在用 / 隔离 / 兼容 / 参考状态清单](REPOSITORY_FILE_INVENTORY.md)
- [Git 分支与 PR 生命周期](BRANCH_LIFECYCLE.md)
- [SC05 ChatGPT 完整工作流操作指南](SC05_CHATGPT_OPERATING_GUIDE.md)
- [SC05 MCP Owner 授权与安全边界](SC05_CHATGPT_MCP_OWNER_BRIDGE.md)
- [SC05 真实 Agent A/B 实验原则与 Runbook](SC05_REAL_AGENT_AB_EVAL_RUNBOOK.md)
- [Development Studio 实验管理 V0.4](DEVSTUDIO_EXPERIMENTS_V04.md)
