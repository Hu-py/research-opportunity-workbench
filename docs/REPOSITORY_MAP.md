# Research Atlas 仓库总览与系统边界

> 审计日期：2026-11-16  
> 当前整理分支：`chore/repo-governance-sc05-chatgpt-20261116`  
> 本文描述仓库结构和已核实的运行入口。文件存在不等于功能已部署，CI 通过也不等于真实科研质量已通过。

## 1. 项目目标

Research Atlas 是团队共享的科研智能工作台。当前工程目标不是把所有功能塞进一个 Agent，而是让不同入口复用同一套后端能力、身份权限和持久化记录。

本阶段的最终验收目标：

**能够直接在 ChatGPT 中创建、运行、追踪和分析一整组真实 SC05 A/B 实验，并把每轮实验记录长期保存。**

## 2. 当前系统拓扑

```text
                         ┌──────────────────────────┐
                         │      Researcher          │
                         │  ChatGPT / Browser UI    │
                         └────────────┬─────────────┘
                                      │
                  ┌───────────────────┴───────────────────┐
                  │                                       │
          ChatGPT MCP + OAuth                     Vercel Next.js
                  │                               Browser / Server
                  │                                       │
                  │                               same-origin API proxy
                  └───────────────────┬───────────────────┘
                                      │
                              Render FastAPI
                              backend/api.py
                                      │
                  ┌───────────────────┼────────────────────┐
                  │                   │                    │
              PostgreSQL          Model Gateway       OpenAlex / APIs
           source of truth       DeepSeek / other       metadata
                  │
          ┌───────┴────────┐
          │                │
       SC05 runs       Development Studio
      checkpoints       experiment registry
          │
      Worker / inline queue
          │
      private R2 archive (optional)
```

两条用户入口是分开的：

- **ChatGPT → Render `/mcp`**：通过 OAuth Authorization Code + PKCE 授权，直接调用 Owner 范围内的 SC05 工具。
- **Browser → Vercel → Render**：网页使用同源 Next.js 路由和服务端代理，浏览器不持有后端 Bearer Token、模型密钥、数据库凭据或 R2 密钥。

PostgreSQL 是实验状态、检查点、权限和轮次记录的权威来源。R2 是可选的私有归档，不替代数据库。

## 3. 主要运行入口

| 层 | 入口 | 作用 | 当前定位 |
|---|---|---|---|
| Web 首页 | `frontend/app/page.tsx` | 重定向到批准的 Research Atlas 页面 | 当前入口 |
| Web 主页面 | `frontend/public/research-atlas-v0.5.html` | Research Atlas 主工作界面 | 当前入口 |
| Developer Studio | `frontend/app/devstudio/route.ts` | 服务端认证后渲染批准的开发者中心 HTML | 当前入口 |
| Developer Studio 模板 | `frontend/lib/devstudio-approved-html.ts` | 已批准页面内容 | 当前依赖 |
| Developer Studio 交互桥 | `frontend/lib/devstudio-live-bridge.ts` | 真实后端数据与交互 | 当前依赖 |
| Next.js API | `frontend/app/api/` | 登录、同源代理、预览环境测试等 | 当前依赖 |
| FastAPI | `backend/api.py` | 主 API、身份、研究任务和功能路由注册 | 主后端入口 |
| SC05 REST | `backend/sc05_eval_api.py` | 论文输入、A/B 运行、预算、检查点、盲评 | SC05 核心 |
| SC05 MCP | `backend/sc05_agent_bridge.py` | ChatGPT OAuth、工具注册、A/B 编排和轮次记录 | ChatGPT 接入核心 |
| SC05 worker | `backend/sc05_worker.py` | PostgreSQL 队列消费、授权检查、执行状态 | 云端执行组件 |
| SC05 pipeline | `backend/sc05_paper_only.py` 等 | 论文理解、诊断、科学价值门控和质量审查 | 实验执行核心 |
| Python 包入口 | `research_workbench/core.py` | SQLAlchemy Base、数据库连接和共享数据模型 | 数据层核心 |
| 独立开发追踪器 | `dev-tracker/` | GitHub Issue / PR / Commit / CI 追踪 | 独立 Vercel 项目 |

## 4. 功能模块边界

### A. 科研发现与 Research Radar

主要代码：`backend/discovery.py`、`backend/discovery_runner.py`、`backend/llm_discovery.py`、`backend/research_sources.py`、`backend/radar_pipeline.py`、`backend/radar_trial.py`、`backend/weekly_synthesis.py`。

职责：OpenAlex 文献发现、来源目录、候选审核、Radar A/B 采集、周报和研究机会更新。

相关自动化位于 `.github/workflows/`，包括 OpenAlex Radar、Radar B Collector 和 weekly/daily 工作流。

### B. Research Agent 与科研方法能力

主要代码：`backend/agent.py`、`backend/ai_lab.py`、`backend/scientific_agent.py`、`backend/scientific_tools.py`、`backend/scientific_tournament.py`、`backend/skill_loader.py`。

职责：研究问题探索、工具调用、方法迁移、候选研究方向生成和评测。

`skills/` 保存版本化研究方法指令。Skill 是 Agent 的行为规范，不是任意 Python 代码执行入口。

### C. Research Profile 与团队数据

主要代码：`backend/profile_intelligence.py`、`backend/profile_database.py`、`backend/repository.py`、`backend/cusp.py`、`backend/interests.py`、`backend/research_evidence_export.py`。

职责：团队画像、成果与数据资产登记、研究兴趣、证据清单和授权导出。

### D. SC04 / SC05 个人科研实验

- SC04 个人研究演化：`backend/sc04_evolution.py`、`backend/research_evolution_api.py`、`backend/research_evolution_runner.py` 及相关验证模块。
- SC05 智能体科研工作流评测：`backend/sc05_eval_api.py`、`backend/sc05_agent_bridge.py`、`backend/sc05_worker.py`、`backend/sc05_paper_only.py`、`backend/sc05_science_gate.py`、`backend/sc05_research_diagnosis.py`、`backend/sc05_quality.py`、`backend/sc05_replay.py`、`backend/sc05_r2_artifacts.py`。

SC05 的研究对象是 Research Atlas Agent 的完整科研工作流，不是对上传论文开展新的实证数据分析。A/B 两组必须共享来源和冻结证据，先运行 baseline，再运行 treatment，最后盲评和解盲。

## 5. SC05 ChatGPT 实验闭环

当前代码中的 ChatGPT 工具覆盖：

1. 读取 Owner 论文与实验清单、预算和执行器状态。
2. 通过 `create_paper_case` 保存提取后的论文页面文本；超过 MCP 请求限制的 PDF 使用已认证网页上传入口。
3. 创建 `science_gate_off` / `science_gate_on` A/B 配对。
4. 成对预检，验证来源哈希、pipeline 哈希、冻结证据、检查点、执行器和预算。
5. 顺序启动：baseline 完成后才能启动 gate-on。
6. 读取匿名 A/B 报告，分别保存盲评。
7. 两组评分完成后解盲比较。
8. 维护带分类、问题、方法、实验内容、状态、结果、后续和详细记录的实验轮次台账。

**代码实现、部署、ChatGPT 工具发现、真实模型执行是四个独立验收层。**本仓库不把 CI 的 mock LLM 测试当成真实 DeepSeek 科研质量结果。

## 6. 部署与当前边界

- Vercel：Next.js 前端；服务端环境变量必须保持 server-only。
- Render：FastAPI 后端与隔离测试服务。
- PostgreSQL：持久化实验、用户、任务、审计和检查点。
- R2：可选私有归档；数据库仍是 source of truth。
- GitHub Actions：CI、定时数据采集、同步与测试。

Render 隔离测试服务 `research-atlas-devstudio-e2e-ejmh` 的自动部署为关闭（`autoDeploy=no`）。截至 2026-11-16 本次审计，最新观察到的 Live deploy commit 为 `262f3b053bb8a3910aed85bda1665073fcfad5f1`；本整理分支的后续代码尚未部署。Render 应用日志还显示 inline worker 已启动且 `live_deepseek_enabled=True`，因此当前服务具备触发真实付费模型调用的条件。每次部署前必须核对分支、commit、数据库和环境变量；不得把测试服务改指生产数据库。

截至本次审计，仓库有独立 staging 分支和多个未合并 PR。当前 SC05 整理分支不代表 Render 或 ChatGPT 已经运行了最新代码。请以 [分支生命周期](BRANCH_LIFECYCLE.md) 和 [SC05 ChatGPT 操作指南](SC05_CHATGPT_OPERATING_GUIDE.md) 为准。

## 7. 验收分层

| 验收层 | 通过条件 | 不能替代什么 |
|---|---|---|
| 静态代码 | Python compile、TypeScript 检查 | 不能证明接口已部署 |
| CI | 后端集成测试、前端构建、隔离测试 | 不能证明真实模型质量 |
| Render | 当前 commit、健康检查、PostgreSQL worker probe | 不能证明 DeepSeek 已成功执行 |
| ChatGPT MCP | OAuth、tools/list、读写 scope、真实工具调用 | 不能证明 A/B 科研质量 |
| 真实实验 | 两组模型运行、检查点、token、盲评和解盲 | 不能自动证明跨论文泛化 |
| 科研质量 | 独立评价、失败归因、多个 held-out papers | 不能由单个成功案例证明 |

## 8. 相关索引

- [文件使用状态清单](REPOSITORY_FILE_INVENTORY.md)
- [分支与 PR 生命周期](BRANCH_LIFECYCLE.md)
- [SC05 ChatGPT 操作指南](SC05_CHATGPT_OPERATING_GUIDE.md)
- [SC05 MCP 原理与安全边界](SC05_CHATGPT_MCP_OWNER_BRIDGE.md)
- [部署说明](../DEPLOYMENT.md)
- [独立开发追踪器](../dev-tracker/README.md)
