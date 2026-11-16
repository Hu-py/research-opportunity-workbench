# Git 分支与 Pull Request 生命周期

> 审计日期：2026-11-16。分支状态会随 PR 合并、Render 部署和 Vercel 项目绑定变化；本文件是治理规则，不是 GitHub 实时 API。

## 1. 分支角色

| 分支 | 角色 | 规则 |
|---|---|---|
| `main` | 默认主线 / 最终发布目标 | 只接收通过 CI、审查部署影响和迁移风险的 PR |
| `experiment/devstudio-postgres-e2e-20261114` | 当前 Render 隔离 E2E / SC05 staging 线 | Render 服务曾绑定此分支且自动部署关闭；未核对数据库前不得改分支或改服务 |
| `chore/repo-governance-sc05-chatgpt-20261116` | 本轮仓库治理与 SC05 MCP 完整工作流修复 | 从 staging 分支建立；先跑 CI，再向 staging 提 PR |
| `feature/*` | 短期功能开发 | 一项能力一个分支，PR 合并后清理 |
| `fix/*` | 缺陷修复 | 一项修复一个分支，合并后清理 |
| `experiment/*` | 受控科研实验或部署试验 | 必须声明数据、模型成本、隔离环境、实验记录和退出条件 |
| `docs/*` | 文档结构或治理自动化 | 不混入业务代码，文档移动保留历史路径兼容或明确迁移表 |

## 2. 当前关键部署关系

已核实的 Render 隔离服务：

- 服务：`research-atlas-devstudio-e2e-ejmh`
- URL：`https://research-atlas-devstudio-e2e-ejmh.onrender.com`
- 代码分支：`experiment/devstudio-postgres-e2e-20261114`
- 自动部署：关闭（`autoDeploy=no`）
- 数据库：隔离测试 PostgreSQL

因此：向 staging 分支提交代码不等于 Render 已部署。每次发布都要核对 Render 的当前 live deploy commit，并在手动部署后重新做健康检查和 MCP 检查。

## 3. 2026-11-16 已观察到的未合并 PR

### 当前主链路 / 需要协调依赖

| PR | 分支 → 目标 | 主题 | 建议 |
|---|---|---|---|
| #90 | `experiment/sc05-r2-cloud-ab-20261115` → staging | SC05 Worker 与 R2 归档 | 当前 SC05 云端执行主链路，优先审查 |
| #64 | staging → `feature/unified-devcenter-v03-release` | Render PostgreSQL E2E | 与 #63 的发布分支有关，先核对依赖 |
| #65 | `feature/owner-invitations-v01-20261114` → unified DevStudio | Owner / 邀请 | 与团队账号正式发布相关 |
| #63 | unified DevStudio → `main` | 开发者中心 V0.3 集成 | 上述分支的主要发布父分支 |
| #89 | `feat/r2-storage-smoke-20261115` → `main` | R2 存储烟测 | 与 staging SC05 归档分开审查 |
| #71 | DevStudio GitHub sync → governance branch | GitHub 活动同步 | 先确认基础分支和 #58 的关系 |

### 文档 / 治理 PR

| PR | 分支 → 目标 | 主题 | 建议 |
|---|---|---|---|
| #56 | `docs/reorganize-v1-20261113` → `main` | 文档分类与历史试点归档 | 与本清单互补；合并前核对新增加的 SC05 文档 |
| #55 | `docs/agent-map-auto-update-20261113` → `main` | Agent Maintenance Map 自动维护 | 先检查脚本是否能在当前仓库和当前分支正确运行 |

### 需要重新确认是否继续的较早 PR

截至审计时仍开放、但最近更新较早的 PR：#70、#69、#62、#58、#57、#50、#49、#48、#33、#32、#30。它们涉及科研 Skill、Research Advisor、Supabase MCP、研究发现和方法实验。

这些 PR 暂列为 **PARKED / 需要 Owner 决策**，不代表代码无用，也不应自动删除。每个 PR 应选择：继续、拆分、合并到新的目标分支、关闭并归档，不能长期保持无人负责的 Draft 状态。

## 4. 合并规则

1. 先核对 PR 的 base branch。不要把 staging 专用代码误合并到 `main`。
2. 一个 PR 尽量只包含一个可描述、可测试的目的。
3. 业务代码 PR 必须提供：问题、方案、影响范围、测试、部署目标、数据库迁移和回滚说明。
4. 涉及模型调用的 PR 必须区分 mock 测试与真实模型测试，并声明费用和授权边界。
5. 涉及 PostgreSQL / R2 / OAuth 的 PR 必须说明密钥位置、隔离环境、数据保留和备份。
6. 合并后更新本文件或由后续自动化同步分支与 PR 状态。

## 5. 分支清理规则

- **不得删除仍被 Render / Vercel 服务绑定的分支。**
- **不得删除有未合并 PR 的分支。**
- 已合并分支只有在确认无部署绑定、无工作流引用、无外部文档链接后才可删除。
- 长期实验分支如需保留，必须标注用途、数据位置、成本状态、负责人和最后验证日期。
- 本轮没有删除任何分支。

## 6. 推荐的长期工作方式

- `main`：可发布的稳定主线。
- `staging`（后续可将当前实验分支改名或建立正式分支）：隔离部署与端到端验收。
- `feature/*`、`fix/*`、`docs/*`：短期 PR 分支。
- `experiment/*`：有明确实验记录的短期实验分支，结束后归档结论，不长期承载产品主线。

**原则：一个长期运行的服务只绑定一个明确的部署分支；一个 PR 只解决一个明确的问题；一个实验结果必须能追溯到代码、来源、模型、检查点和评价记录。**
