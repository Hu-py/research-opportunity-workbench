# Research Atlas Development Studio — GitHub 自动同步 V0.1

**状态：独立 Draft PR，未合并 / 未部署 / 未配置 secrets。** 本功能建立在 [Development Studio P0 草稿 PR #58](https://github.com/Hu-py/research-opportunity-workbench/pull/58) 的数据表和七屏界面上。GitHub 已提交代码不等于线上已启用。

## 1. 目标与边界

用户在 [Hu-py/research-opportunity-workbench](https://github.com/Hu-py/research-opportunity-workbench) 提交代码、创建/更新/合并 PR、处理 Issue、GitHub Actions CI 完成后，自动同步可信的工程元数据到 Development Studio「研发总览」中的 GitHub 活动记录。页面加载时读取数据库，已登录的团队成员约每 60 秒只读刷新一次活动摘要。

**同步范围（不是科研实验自动验收）**

| 来源事件 | 去重主键 | 展示状态 | 说明 |
| --- | --- | --- | --- |
| GitHub `push` | 最新 commit SHA | 已记录 | 分支、最后提交摘要、推送数量；非完整逐 commit diff |
| `pull_request_target` | PR 编号 | draft/open/closed/merged | 记录工程 PR 现状；不等于独立批准 |
| `issues` | Issue 编号 | open/closed | 记录技术台账变化 |
| `workflow_run` (CI) | GitHub Actions run ID | success/failure/cancelled 等 | 仅 **CI 工程状态**。对应实验 Run 若已手动绑定相同链接，则更新为 `ci_*`，不添加人工评价或科研质量分数 |

自动同步不创建或批准 `DevChange`、`DevExperiment`、`DevEvaluation`；也不修改学术源目录、科研周报、生产部署、团队角色或模型密钥。GitHub 的 workflow 成功只说明该工作流报告成功，**不证明生产部署与科研质量**。

## 2. 结构

```text
GitHub（push / PR / issue / CI 完成）
   |
   v
GitHub Actions: .github/workflows/devstudio-github-sync.yml
   | 无 checkout；不执行 PR 代码；HMAC SHA256 签名
   v
POST <BACKEND_URL>/api/devstudio/github/webhook
   | 校验仓库名称 + secret + 签名 + delivery ID + 允许的事件类型
   v
devstudio_github_activity + devstudio_github_deliveries
   | 根据稳定主键 upsert，防重复发送与旧 PR 状态覆盖
   v
GET /api/devstudio/github/activity（需团队登录）
   | 页面 60s 读取
   v
Development Studio / 研发总览 / GitHub 自动同步
```

后台仍复用现有 SQLAlchemy 数据库。全量请求体仅用于入站签名核验和有限字段抽取；**不保存 PR 正文、Issue 正文、源码、密钥或私人研究数据**。被存储的字段为类型、编号/sha、标题、标准化 GitHub URL、工程状态、GitHub 用户名、分支、事件时间、简短说明、接收时间；保留有限去重 delivery ID/digest。网页仅渲染来自受限仓库的 URL。

## 3. 启用步骤（部署后，由仓库 Owner/管理员完成）

**后台服务环境变量：**

- `TEAM_AUTH_ENABLED=true`，必须已完成团队登录机制。
- `DEVSTUDIO_GITHUB_SYNC_ENABLED=true`，新功能默认关闭。
- `DEVSTUDIO_GITHUB_SYNC_SECRET=<生成的独立随机秘密，建议 32 字节以上>`，不能沿用 Owner 登录口令。
- 保持 `API_BEARER_TOKEN` 的既有配置（浏览器访问由 Next.js 服务端代理转发）。Webhook 入口使用独立 HMAC 签名认证，不接受用户浏览器传 secrets。

**在 GitHub 仓库 Settings → Secrets and variables → Actions → Repository secrets 配置：**

- `DEVSTUDIO_SYNC_URL` = `https://<实际可访问后端地址>/api/devstudio/github/webhook`（**正式 FastAPI 地址，不是登录页或 Next.js 页面地址**）。
- `DEVSTUDIO_SYNC_SECRET` = 与后台 `DEVSTUDIO_GITHUB_SYNC_SECRET` 完全相同的值。

安全性：GitHub workflow 不 checkout PR 代码、无第三方动作；即使外部人员提 PR，也仅把 GitHub 事件文件中的**元数据**转发到签名后端。签名和密钥从不出现在 UI、GitHub 提交或 CI 日志。不要设置成明文 GitHub Repository Variables。

**注意：** GitHub 对 `pull_request_target`、`workflow_run` 等事件的 workflow 生效依赖默认分支具备本 workflow 文件；因此此 Draft PR 在合并前**不会自动上线**。GitHub Actions secrets 不会由本代码自动创建。

## 4. 首次验证步骤

1. 合并经评审的 Development Studio P0 和同步 PR，部署 FastAPI 和 Next.js，并确认数据库完成安全备份/迁移。
2. 配置 GitHub Actions 两项 secrets 和后台两个新环境变量。
3. 在 Development Studio 以团队账号登录，打开「研发总览」：此时显示「已配置签名接口 · 尚未接收事件」。
4. 提交无敏感信息的测试 commit，创建测试 PR 和 Issue，并让 CI 完成；待 GitHub Actions 的 `Development Studio GitHub sync` 工作流执行成功后，读取 `GET /api/devstudio/github/activity`，确认自动显示事件。
5. 绑定对应 GitHub Actions run 到一个**手动登记**的实验，验证 `ci_success` 只改变 Run 的工程状态，科研质量评分仍为空。
6. 重新运行相同 delivery 或重发 PR 旧事件，确认去重、不会被旧状态覆盖。
7. 关闭 `DEVSTUDIO_GITHUB_SYNC_ENABLED` 后，入口返回 503；Team Viewer 可看活动，无团队登录者不能读取。

### 故障排查

- GitHub workflow 显示 skipped/no secrets：未在仓库 Actions Secrets 配置同步地址或密钥。
- 401：签名或两端密钥不匹配；确认地址指向后端 API，而不是 Next.js 页面。
- 503：团队认证未启用、功能开关关闭或后台密钥长度不足。
- 422：事件格式、仓库身份或 delivery ID 未通过验证。
- HTTP 5xx / GitHub Actions failure：后端临时不可用；GitHub Actions 手动 Re-run job 后同一事件会幂等覆盖/忽略；流水不保证百分百零延迟，需要后续补充周期核账/补录机制。

## 5. 具体适用于儿童健康外推三探针

- [PR #70](https://github.com/Hu-py/research-opportunity-workbench/pull/70) 和相关 GitHub CI 在该功能上线后的**新变更**将自动显示于「GitHub 活动」。
- 既有 PR #70 **不会因为安装了同步服务就自动补回此前所有历史事件**；补历史记录需单独执行 GitHub API 核账/回填或人工将 PR 和 Run 绑定到对应实验。
- [SC01 论文探针试运行报告](https://github.com/Hu-py/research-opportunity-workbench/blob/experiment/urban-health-graph-closed-loop-20261114/experiments/urban_health_graph_2026_11_14/SC01_TEAM_THREE_PROBE_TRIAL.md) 必须经研究者确认后才可成为正式 `DevExperiment` 和评价记录；不能因为 PR 的 CI success 自动生成「科学审核通过」。

## 6. 回归检查

```bash
python -m pytest -q tests/test_devstudio_github_sync.py
python -m pytest -q
cd frontend && npm run typecheck && npm run build
```

测试采用本地 HMAC 签名与伪 GitHub 事件，不需要真实 webhook、付费模型或生产数据库。正式验收还需真实的 GitHub Actions → 部署后端 → Studio 页面联调。同步层可以独立关闭；不影响现有研究工作流与审批逻辑。
