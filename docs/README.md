# Research Atlas 文档目录

> 本目录按 Research Atlas Documentation System V1.0 整理。这里列出的是**现有仓库文档**，并不意味着新的 PRD V0.3 已批准或写入 GitHub。

- 总入口：仓库根目录 [README](../README.md)
- 部署入口：[DEPLOYMENT](../DEPLOYMENT.md)
- 研发看板：[dev-tracker](../dev-tracker/README.md)

## 文档分类

### AI / Agent 能力 (`03-ai/`)

| 文件 | 用途 | 类型 |
| --- | --- | --- |
| [AI_RESEARCH_LAB_P2.md](03-ai/AI_RESEARCH_LAB_P2.md) | AI 选题四阶段研究实验台 | AI 原型说明 |
| [AUTONOMOUS_RESEARCH_EVOLUTION.md](03-ai/AUTONOMOUS_RESEARCH_EVOLUTION.md) | 自主科研演化与审查流程 | 实验性工作流 |
| [OPPORTUNITY_ENGINE_P0_P1.md](03-ai/OPPORTUNITY_ENGINE_P0_P1.md) | 研究机会引擎 P0/P1 设计与边界 | 功能实施参考 |
| [RESEARCH_PROFILE_STUDIO.md](03-ai/RESEARCH_PROFILE_STUDIO.md) | 科研画像 AI 草稿与审核 | AI 能力说明 |
| [SCIENTIFIC_TOOL_REGISTRY.md](03-ai/SCIENTIFIC_TOOL_REGISTRY.md) | 科研工具注册与试验智能体 | 工具与 Agent 能力参考 |
| [research-agent-game-replay.md](03-ai/research-agent-game-replay.md) | 多智能体研究回放及实验运行 | Agent UI/运行参考 |

### 系统架构 (`04-architecture/`)

| 文件 | 用途 | 类型 |
| --- | --- | --- |
| [ARCHITECTURE.md](04-architecture/ARCHITECTURE.md) | 系统架构与接口边界（早期版本） | 架构参考，需对照现状维护 |

### 科研数据与知识 (`05-data/`)

| 文件 | 用途 | 类型 |
| --- | --- | --- |
| [CUSP_DATA_REGISTER.md](05-data/CUSP_DATA_REGISTER.md) | CUSP 数据目录与访问边界 | 数据治理参考 |
| [TEAM_RESEARCH_ARCHIVE.md](05-data/TEAM_RESEARCH_ARCHIVE.md) | 团队研究成果和数据资产 | 科研数据治理 |

### API 与学术数据集成 (`06-api/`)

| 文件 | 用途 | 类型 |
| --- | --- | --- |
| [RADAR_B_EVIDENCE_PIPELINE.md](06-api/RADAR_B_EVIDENCE_PIPELINE.md) | Radar B 数据采集与证据接口 | 外部数据管道参考 |

### 团队治理与权限 (`08-governance/`)

| 文件 | 用途 | 类型 |
| --- | --- | --- |
| [TEAM_SETUP.md](08-governance/TEAM_SETUP.md) | 团队账号、权限与部署 | 团队治理/部署参考 |

### 部署、调度与开发维护 (`09-operations/`)

| 文件 | 用途 | 类型 |
| --- | --- | --- |
| [DEVELOPMENT_STUDIO.md](09-operations/DEVELOPMENT_STUDIO.md) | 开发进度、交付和兴趣扫描 | 开发维护说明 |
| [RESEARCH_RADAR.md](09-operations/RESEARCH_RADAR.md) | 每日采集、周报与运行配置 | 运行配置说明 |

### 2026 年历史试验归档 (`archive/2026-pilots/`)

| 文件 | 用途 | 类型 |
| --- | --- | --- |
| [FREE_AGENT_TEST.md](archive/2026-pilots/FREE_AGENT_TEST.md) | Render Free 科研 Agent 集成测试 | 历史试验记录 |
| [HEADLESS_PROFILE_AUDIT.md](archive/2026-pilots/HEADLESS_PROFILE_AUDIT.md) | 科研画像无前端审计流程 | 历史试验记录 |
| [SCIENCE_STAGING_PILOT.md](archive/2026-pilots/SCIENCE_STAGING_PILOT.md) | 2026-11-05 科学实验 staging 试点 | 历史试验记录 |

## 暂无正式文档的类别

以下类别属于目标文档体系，但尚未从现有文件中发现可直接归入的正式文档，**不应将讨论草案误作已批准规范**：

- `00-strategy/`：产品定位与路线图。
- `01-product/`：正式 PRD、功能注册表、验收标准。
- `02-experience/`：信息架构、页面和交互规范。
- `07-evaluation/`：AI 评价和系统测试规范。

## 阅读与维护规则

1. **主文档与历史记录分开。** `archive/2026-pilots/` 收纳曾经有用、但带有时间和实验环境限制的试点指南；不可作为当前部署指令直接照做。
2. **文档不等于运行成功。** 早期技术文档可能描述原型、未验证的试验或过时部署，应结合当前代码、CI、真实运行日志和人工验收核对。
3. **不重复保管源代码或 Skill。** Agent 实现以 `backend/` 为准，Skill 以 `skills/` 为准，运行流程以 `.github/workflows/` 为准；文档说明职责和限制。
4. **变更需关联实现。** 修改 Agent、API、数据或权限时，连同相关文档和测试一起提交 PR。
5. **保护私人资料。** 该仓库是公开仓库，不存放聊天记录、未发表材料、数据库凭据或其他私人数据。
6. **旧链接兼容。** 原先经 README 或部署指南公开引用的四个旧路径保留简短跳转页：`ARCHITECTURE.md`、`TEAM_SETUP.md`、`DEVELOPMENT_STUDIO.md` 和 `research-agent-game-replay.md`。

## 本次清理决策

- 原有 Markdown 文档 **16 份**：**13 份分类保留**，**3 份转为历史归档**。
- 归档：`FREE_AGENT_TEST.md`、`HEADLESS_PROFILE_AUDIT.md`、`SCIENCE_STAGING_PILOT.md`。
- 未永久丢弃任何正文：它们包含运行边界、历史测试记录或部署证据；没有足够证据证明可以无风险删除。
- 四个高频旧路径保留仅指向正式位置的兼容页；其它旧路径因分类移动而移除。
- 本次**仅整理既有文档**，不把尚未评审通过的新 PRD 或前端设计写成正式规范。
