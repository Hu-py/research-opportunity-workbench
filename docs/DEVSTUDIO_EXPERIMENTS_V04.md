# Development Studio｜实验管理 V0.4（隔离测试版）

> 2026-11-14 · 所属分支 `feature/devstudio-experiments-v04-20261114`，基于 `experiment/devstudio-postgres-e2e-20261114`。本版本只面向现有 **Owner/Admin** 的 Development Studio 测试入口，不改变 Research Atlas 正式前台、GitHub 自动化或科研成果评价结论。

## 为什么需要这一版

V0.3 仅能创建实验、关联 GitHub Run 和追加人工评分，无法维护持续演化的实验档案。V0.4 让实验本身成为版本化科研研发对象：

- **实验分类**：所属模块、实验目标（质量/性能/泛化/覆盖/可靠性/方法/可用性）、使用场景（Radar A/B、SC01/02/03、平台）、变更对象（来源、工作流、提示词、模型、Skill、前后端、数据、评价）。
- **核心要素**：实验名称、假设、基线、实验方法、输入快照、追踪指标、预期结果、阶段结论、下一步行动、关联的正式变更 ID。
- **生命周期**：`planned → running → review → completed`，以及 `blocked`、`archived`、重新开启。状态跳转由后端核验；不能直接跳过复核，也不能在缺少人工运行评价时标记完成。
- **版本追踪**：每次修改增加修订号、变更字段前后值、操作者和时间；通过 `expected_revision` 防止并发覆盖，返回 HTTP 409 促使刷新。归档保留历史，不删除数据库记录。
- **运行与评价**：沿用原 `devstudio_runs` 与 `devstudio_evaluations`，外部 GitHub Actions 仅标记未核验的引用，人工评价只追加不能覆盖。关联运行不触发真实 CI 执行。
- **检索筛选**：按模块、目标、场景、状态、关键字过滤；归档默认隐藏、可显式包含。支持旧版实验直接读取与继续编辑。
- **同站 UI**：原 `/devstudio` 增加「完整实验管理」入口，新页面为 `/devstudio/experiments`；要求真实 Owner/Admin 会话，沿用服务器代理与黑白极简风格。

## 技术实现

FastAPI `backend/experiment_management.py` 为独立扩展模块，沿用原 `backend/devstudio.py`。新建两张 PostgreSQL/SQLite 表：

| 表 | 用途 |
|---|---|
| `devstudio_experiment_profiles` | 每个实验的分类、方法、预期结果、结论、后续行动、revision、最近编辑人 |
| `devstudio_experiment_events` | 不可通过普通 API 修改的实验变更事件，每次保存追加差异和操作者 |

**已有 `devstudio_experiments`、`devstudio_runs`、`devstudio_evaluations` 不改列、不删除、不重新编号。** 原表的数据由新接口按默认 `revision=0` 显示，第一次编辑时补建 Profile 并建立第 1 条 V0.4 事件。不会伪造旧数据的历史版本。

新端点（均在 `/api/devstudio` 下，使用现有团队会话和 server-only API Bearer）：

| 方法 | 路由 | 用途 |
|---|---|---|
| GET | `/experiment-management` | 列表与筛选 |
| GET | `/experiment-management/{id}` | 单条详情 |
| POST | `/experiment-management` | 创建并初始化版本 1 |
| PATCH | `/experiment-management/{id}` | 编辑/推进状态，校验 expected_revision |
| GET | `/experiment-management/{id}/history` | 变更历史 |

仍使用原 `/experiments/{id}/runs`、`/runs/{id}/evaluations` 追加运行与评价。

## 权限与责任

- Web 管理页：Owner/Admin 可进入。科研成员/只读成员不能通过该页面操作。
- 后端沿用 V0.3 的 Researcher 新增/编辑实验许可（团队共享台账），Viewer 仅查看。未来如果需要限制为 Owner/Admin 独占写权限，应在主权限规范中单独审议并同步修改接口和前端。
- 所有实验编辑/状态变更同时追加业务版本事件和 `team_audit` 审计事件。
- 任何实验被标记「已完成」只表示台账中存在人工评价记录，不代表科研结论已被外部验证。

## 验收清单

1. **旧记录兼容**：此前浏览器创建的实验仍然显示，修订号默认 0，可进行首次编辑，旧运行和评价仍保留。
2. **编辑与刷新**：创建 → 修改分类 → 刷新页面 → 信息不丢失；历史里能看到变更前后值。
3. **筛选**：目标、场景、状态和关键词正确；归档前后筛选正确。
4. **协作安全**：较旧 expected_revision 提交返回 409；无效分类 422；Viewer 写入 403；未登录 401。
5. **复核门槛**：不能计划直接完成；运行→待复核后没有评价也不能完成；添加评价后方可完成；已归档需先重新开启。
6. **运行证据**：GitHub Run 仅登记关联链接，默认未核验；人工评分不影响生产发布。
7. **部署**：先在隔离的 Render E2E PostgreSQL Schema 测试，Vercel Preview 仅使用测试分支环境变量，绝不覆盖生产域名或两个既有 Render 后端。

## 当前非目标

自动执行实验、自动比较模型指标、导入 DeepSeek 对话运行、自动抓取 GitHub Actions 状态、科学证明报告、Excel 批量导入、跨项目实验依赖图均不在此次完成范围。后续可在稳定的数据模型上按需求新增。
