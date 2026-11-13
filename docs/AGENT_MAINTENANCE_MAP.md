# Agent Maintenance Map｜Research Atlas

> 初始核验：2026-11-13；基准代码提交 `2b5e2c8878b5e360c93b838a6e6d31432bddf943`。
> 本文件今后由 GitHub Actions 自动更新源文件证据和变更提醒，结论状态须人工复核。

## 概览

共 37 项能力：已实现 19，部分实现 11，未实现 7。

## 能力与证据目录

| ID | 能力 | 人工核验状态 | 代码证据路径 |
|---|---|---|---|
| A1 | Agent A：应用与实践 | 未实现 | `config/agent_profiles/application.json` |
| A2 | Agent B：前沿与问题重构 | 未实现 | `config/agent_profiles/frontier.json` |
| A3 | Agent C：技术与方法 | 未实现 | `config/agent_profiles/methodology.json` |
| E1 | 通用 GPT Research Agent | 已实现 | `backend/agent.py` |
| E2 | DeepSeek AI 选题分析工作流 | 已实现 | `backend/ai_lab.py` |
| E3 | 自主调用学术工具的科学探索 | 已实现 | `backend/scientific_agent.py` |
| E4 | 多 Agent 博弈与研究演化 | 已实现 | `backend/scientific_tournament.py`、`backend/research_evolution_runner.py` |
| D1 | OpenAlex Radar A 定时数据采集 | 已实现 | `.github/workflows/openalex-radar-weekly.yml` |
| D2 | Radar B AI/CS 方法采集 | 已实现 | `.github/workflows/radar-b-collector.yml` |
| D3 | 学术来源库与期刊会议管理 | 已实现 | `backend/research_sources.py`、`frontend/components/AcademicSourceRegistry.tsx` |
| D4 | 团队作者自动监测 | 部分实现 | `backend/repository.py` |
| D5 | LLM 语义检索规划 | 部分实现 | `backend/llm_discovery.py`、`backend/discovery_runner.py` |
| D6 | 多轮检索覆盖缺口迭代 | 部分实现 | `backend/discovery_runner.py`、`backend/scientific_agent.py` |
| D7 | 引用网络与跨学科检索工具 | 部分实现 | `backend/scientific_tools.py` |
| P1 | 论文元数据及 DOI 去重 | 已实现 | `research_workbench/core.py` |
| P2 | 候选论文人工审核 | 已实现 | `backend/discovery.py` |
| P3 | 语义相关性及方法迁移评价 | 已实现 | `backend/llm_discovery.py` |
| P4 | 全文阅读及逐段证据定位 | 未实现 | `backend/fulltext_reader.py` |
| K1 | 任务级一级主题与子类分类 | 未实现 | `backend/topic_taxonomy.py` |
| K2 | 议题方法场景知识结构化 | 部分实现 | `backend/ai_lab.py`、`skills/method_transfer/SKILL.md` |
| K3 | 论文与结论的证据关联 | 部分实现 | `backend/scientific_agent.py`、`research_workbench/core.py` |
| K4 | 跨论文方法输入输出关系 | 部分实现 | `skills/method_transfer/SKILL.md` |
| R1 | 版本化选题及 Markdown 周报 | 已实现 | `backend/radar_pipeline.py`、`research_workbench/core.py` |
| R2 | 层级 Research Brief 与折叠文献 | 部分实现 | `frontend/components/ResearchRadar.tsx` |
| U1 | 团队正式画像和修订历史 | 已实现 | `backend/team.py`、`backend/profile_intelligence.py` |
| U2 | 研究兴趣清单 | 已实现 | `backend/interests.py` |
| U3 | 个人私有研究画像 | 未实现 | `backend/personal_profiles.py` |
| U4 | 本次自由主题与任务限定 | 部分实现 | `backend/tasks.py`、`backend/discovery_runner.py` |
| O1 | GitHub CI | 已实现 | `.github/workflows/ci.yml` |
| O2 | 数据库周报定时调度 | 部分实现 | `.github/workflows/daily.yml`、`.github/workflows/weekly.yml` |
| O3 | Vercel Cron 入口 | 已实现 | `frontend/vercel.json`、`frontend/app/api/cron/weekly-research/route.ts` |
| O4 | 团队账号权限与审计 | 已实现 | `backend/team.py` |
| O5 | 任务阶段记录与追踪 | 已实现 | `backend/tasks.py` |
| O6 | 独立开发追踪面板 | 已实现 | `dev-tracker/app.js`、`dev-tracker/roadmap.json` |
| Q1 | 自动化单测和前端构建 | 已实现 | `.github/workflows/ci.yml`、`tests/test_api_agent.py` |
| Q2 | 论文发现科研质量基准 | 未实现 | `tests/test_literature_quality.py` |
| O7 | Agent Maintenance Map 自动更新 | 部分实现 | `scripts/update_agent_maintenance_map.py`、`.github/workflows/agent-maintenance-map.yml` |

## 自动维护机制

- 新提交影响源文件时：更新证据检查结果、标记需要人工复核的能力；不会自动将“部分实现”改为“已实现”。
- GitHub Actions 在主分支相关变更、每周巡检或手动触发时重新生成本文档，并通过 Pull Request 提请审核。
- 人工确认功能状态后，请修改 `config/agent_maintenance_capabilities.json`，更新状态、证据路径及核验基准。
- 所有变更可通过 GitHub Commit / Pull Request 追溯。

## 近期优先级

1. P0-A：统一临时研究任务输入。
2. P0-B：任务级一级主题/子类动态分类。
3. P0-C：按主题组织重点及延伸文献的 Research Brief。
4. P1：三个专业 Agent 与个人独立画像。

_初始能力判断来自 2026-11-13 的静态代码审计；科研质量不由文件存在性自动证明。_
