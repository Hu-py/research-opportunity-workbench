# Research Atlas 文件使用状态清单

> 审计日期：2026-11-16。此清单用于区分“当前运行依赖”“测试/运维依赖”“隔离环境专用”和“历史参考”。  
> **不以文件年龄、文件名或目录位置判断是否可删除。** 未确认依赖关系的文件标为复核候选，不直接删除。

## 状态定义

| 状态 | 含义 | 删除规则 |
|---|---|---|
| `ACTIVE-RUNTIME` | 当前 Web/API/Agent 运行路径直接使用 | 不得直接删除 |
| `ACTIVE-FEATURE` | 已注册路由或被活跃模块调用，但属于可选功能 | 先确认产品范围和路由 |
| `ACTIVE-SUPPORT` | CI、测试、部署、数据采集、维护脚本依赖 | 需先更新对应工作流 |
| `STAGING-ONLY` | 仅隔离测试/Preview/一次性运维使用 | 正式环境不启用；测试结束后再评估归档 |
| `LEGACY-COMPAT` | 旧界面或兼容路径仍被 CI/部署保留 | 不能仅因非主入口而删除 |
| `REFERENCE-ONLY` | 设计历史、迁移快照、历史试点记录 | 可归档，不代表代码功能废弃 |
| `REVIEW-CANDIDATE` | 尚未完成全仓 import / route / workflow 引用审计 | 不删除，待自动化扫描 |

## 1. 当前主运行链路

| 路径 | 状态 | 用途 / 依赖说明 |
|---|---|---|
| `frontend/app/page.tsx` | ACTIVE-RUNTIME | 首页重定向到批准的 Research Atlas V0.5 页面 |
| `frontend/public/research-atlas-v0.5.html` | ACTIVE-RUNTIME | 当前首页实际加载的主工作界面 |
| `frontend/app/devstudio/route.ts` | ACTIVE-RUNTIME | 校验 Owner/Admin 身份后返回开发者中心 |
| `frontend/lib/devstudio-approved-html.ts` | ACTIVE-RUNTIME | 开发者中心批准版 HTML 模板 |
| `frontend/lib/devstudio-live-bridge.ts` | ACTIVE-RUNTIME | 开发者中心真实数据与 API 交互桥 |
| `frontend/app/api/proxy/[...segments]/route.ts` | ACTIVE-RUNTIME | Next.js 服务端代理到 Render API |
| `frontend/lib/session.ts` | ACTIVE-RUNTIME | 团队会话读取与验证 |
| `backend/api.py` | ACTIVE-RUNTIME | FastAPI 主入口，注册认证、科研和管理路由 |
| `research_workbench/core.py` | ACTIVE-RUNTIME | SQLAlchemy Base、数据库会话和共享科研数据模型 |
| `backend/team.py` | ACTIVE-RUNTIME | 成员、角色、会话和审计记录 |
| `backend/devstudio.py` | ACTIVE-RUNTIME | Development Studio 实验/问题/运行记录 API |
| `backend/tasks.py`、`backend/worker.py` | ACTIVE-RUNTIME | 通用科研任务持久化与 Worker |
| `backend/model_gateway.py`、`backend/model_vault.py` | ACTIVE-RUNTIME | 模型请求与加密模型凭据 |
| `backend/research_budget.py` | ACTIVE-RUNTIME | 模型调用和 token 预算记录 |

## 2. SC05 ChatGPT A/B 实验链路

| 路径 | 状态 | 用途 / 依赖说明 |
|---|---|---|
| `backend/sc05_eval_api.py` | ACTIVE-RUNTIME | Owner 论文输入、A/B Run、冻结证据、预算、检查点、评分 |
| `backend/sc05_agent_bridge.py` | ACTIVE-FEATURE | ChatGPT OAuth/PKCE、MCP 工具、A/B 编排和实验轮次台账 |
| `backend/sc05_worker.py` | ACTIVE-FEATURE | PostgreSQL 队列消费、授权校验和执行器状态 |
| `backend/sc05_paper_only.py` | ACTIVE-RUNTIME | 论文阅读、证据账本、方法诊断和报告生成 |
| `backend/sc05_science_gate.py` | ACTIVE-RUNTIME | 科学价值门控与独立研究问题审查 |
| `backend/sc05_research_diagnosis.py` | ACTIVE-RUNTIME | 证据、机制和研究问题诊断 |
| `backend/sc05_quality.py` | ACTIVE-RUNTIME | 输出质量检查 |
| `backend/sc05_replay.py` | ACTIVE-FEATURE | 已保存检查点的安全验证/恢复 |
| `backend/sc05_r2_artifacts.py`、`backend/r2_storage.py` | ACTIVE-FEATURE | 私有 R2 归档适配器；开关和凭据未启用时不归档 |
| `tests/test_sc05_*.py` | ACTIVE-SUPPORT | SC05 API、MCP、安全、Worker 和论文工作流测试 |

注意：SC05 MCP 已写入代码不等于已部署到 Render，也不等于 ChatGPT 已刷新工具清单。真实 DeepSeek 调用必须有明确用户授权和可用云端执行器。

## 3. 其他活跃功能模块

| 模块 / 路径 | 状态 | 说明 |
|---|---|---|
| `backend/discovery.py`、`backend/discovery_runner.py`、`backend/llm_discovery.py` | ACTIVE-FEATURE | 学术发现、查询规划和候选论文评估 |
| `backend/research_sources.py` | ACTIVE-FEATURE | 学术来源与期刊/会议目录 |
| `backend/radar_pipeline.py`、`backend/radar_trial.py`、`backend/weekly_synthesis.py` | ACTIVE-FEATURE | Research Radar 和周报 |
| `backend/agent.py`、`backend/skill_loader.py` | ACTIVE-FEATURE | 通用 Research Agent 和 Skill 加载 |
| `backend/ai_lab.py`、`backend/scientific_agent.py`、`backend/scientific_tools.py` | ACTIVE-FEATURE | 自主科研探索与工具注册 |
| `backend/scientific_tournament.py` | ACTIVE-FEATURE | 多 Agent 盲评和研究方案博弈 |
| `backend/profile_intelligence.py`、`backend/profile_database.py` | ACTIVE-FEATURE | 团队与个人科研画像 |
| `backend/cusp.py`、`backend/repository.py`、`backend/research_evidence_export.py` | ACTIVE-FEATURE | 数据资产、成果登记和受控证据导出 |
| `backend/research_evolution_api.py`、`backend/research_evolution.py`、`backend/research_evolution_runner.py`、`backend/research_evolution_validation.py` | ACTIVE-FEATURE | 旧团队研究演化引擎及其 API；仍被路由使用 |
| `backend/sc04_evolution.py` | ACTIVE-FEATURE | 独立的 SC04 个人研究演化 |
| `backend/sc04_exploratory_quickstart.py` | ACTIVE-FEATURE | 由 SC04 路由动态调用，不是废弃文件 |
| `backend/task_venue_radar.py` | ACTIVE-FEATURE | 专题期刊/任务雷达 |
| `backend/account_onboarding.py` | ACTIVE-FEATURE | Owner 开通、邀请和密码恢复 |
| `backend/devstudio_github_sync.py`、`backend/devstudio_github_pull.py`、`backend/devstudio_history_import.py` | ACTIVE-SUPPORT | Development Studio GitHub 同步、拉取和历史导入 |
| `backend/experiment_management.py` | ACTIVE-SUPPORT | Development Studio 历史实验管理辅助模块 |

## 4. 测试、部署与自动化

| 路径 | 状态 | 说明 |
|---|---|---|
| `tests/` | ACTIVE-SUPPORT | 后端、API、Agent、权限、SC05、前端辅助和数据管线测试 |
| `.github/workflows/ci.yml` | ACTIVE-SUPPORT | Python 测试、Streamlit 兼容烟测、TypeScript 与 Next.js build |
| `.github/workflows/openalex-radar-weekly.yml`、`openalex-radar-verify.yml` | ACTIVE-SUPPORT | Radar A 数据采集与验证 |
| `.github/workflows/radar-b-collector.yml` | ACTIVE-SUPPORT | Radar B 方法来源采集 |
| `.github/workflows/weekly.yml`、`daily.yml` | ACTIVE-SUPPORT | 定时研究任务 |
| `.github/workflows/devstudio-github-sync.yml` | ACTIVE-SUPPORT | GitHub 活动同步 |
| `.github/workflows/sc05-mcp-live-check.yml`、`sc05-mcp-security.yml` | ACTIVE-SUPPORT | SC05 MCP 部署与安全检查 |
| `scripts/` | ACTIVE-SUPPORT | 数据迁移、隔离测试、仓库维护和部署辅助 |
| `Dockerfile.api`、`Dockerfile.worker` | ACTIVE-SUPPORT | Render API / Worker 容器 |
| `pyproject.toml` | ACTIVE-SUPPORT | Python 主依赖和命令入口 |
| `frontend/package.json`、`frontend/vercel.json` | ACTIVE-SUPPORT | Next.js 构建和 Vercel 路由配置 |
| `dev-tracker/` | ACTIVE-RUNTIME | 独立 Vercel 项目，追踪 Issue / PR / Commit / CI |
| `skills/` | ACTIVE-SUPPORT | 版本化科研方法与 Agent 行为规范 |
| `data/radar/`、`config/` | ACTIVE-SUPPORT | Radar 数据快照、配置与运行清单 |

## 5. 隔离测试专用，不应进入普通生产路径

| 路径 | 状态 | 依据 / 注意事项 |
|---|---|---|
| `Dockerfile.devstudio-e2e` | STAGING-ONLY | 启动隔离 PostgreSQL E2E 服务 |
| `.render/devstudio-e2e.yaml` | STAGING-ONLY | Render 隔离测试 Blueprint |
| `scripts/devstudio_postgres_e2e.py` | STAGING-ONLY | 测试服务启动脚本 |
| `backend/account_preview_sandbox.py` | STAGING-ONLY | 被隔离测试启动脚本调用；模拟收件箱不发送真实邮件 |
| `backend/sc05_operator_once.py` | STAGING-ONLY | 被隔离测试启动脚本调用的一次性操作器，不是普通 API Worker |
| `frontend/app/api/devstudio-e2e/route.ts` | STAGING-ONLY | 仅 Vercel Preview + 专用环境开关 + 隔离后端可用 |
| `frontend/app/account/test-inbox/` | STAGING-ONLY | Preview 模拟收件箱，不能用于真实邮箱验证 |
| `backend/fixtures/`、`data/devstudio/` | STAGING-ONLY / REFERENCE | 历史导入和测试快照；不是生产数据库的实时副本 |

## 6. 旧入口、兼容层和历史资料

| 路径 | 状态 | 说明 |
|---|---|---|
| `app.py` | LEGACY-COMPAT | Streamlit 旧原型；不是当前主 Web 首页，但 CI 仍运行 legacy smoke test |
| `requirements.txt` | LEGACY-COMPAT | 旧 Streamlit 环境依赖；主 Python 工程依赖以 `pyproject.toml` 为准 |
| `research_workbench/ui_theme.py` | LEGACY-COMPAT | Streamlit UI 样式辅助 |
| `backend/team_cli.py` | ACTIVE-SUPPORT | 人工 bootstrap 管理员的 CLI，不是 HTTP 路由 |
| `docs/02-experience/prototypes/` | REFERENCE-ONLY | 设计原型和历史版本；实际前端以 `frontend/` 为准 |
| `docs/*2026*.md`、试点报告和审计文件 | REFERENCE-ONLY | 记录历史状态；不能覆盖当前运行状态 |
| `frontend/components/` | REVIEW-CANDIDATE | 当前首页走 V0.5 静态页面，不能据此断言整个组件目录无引用；完成全仓 import scan 后再决定是否归档 |

## 7. 删除 / 归档前必须执行的检查

1. 全仓搜索 Python import、TypeScript import、动态 import 和字符串路径引用。
2. 检查 `pyproject.toml`、Dockerfile、Render Blueprint、Vercel 配置和 GitHub Actions。
3. 检查测试是否通过 fixture 或启动脚本间接引用该文件。
4. 检查当前部署分支、Preview URL、生产 alias 和外部项目是否依赖该路径。
5. 对历史实验、数据快照和迁移输入，先确认数据库已有持久化副本与备份。
6. 删除只通过独立 PR 执行，并在 PR 中记录替代路径和验证证据。

**本轮不永久删除任何业务代码或历史数据。** 下一轮清理应优先做可自动验证的 import/reference 扫描，再决定是否移动或删除 REVIEW-CANDIDATE。
