# Development Studio V0.4 · GitHub 自动同步与 E2E 联调

**目标环境（隔离测试，不是正式发布）：** Render workspace `Booooom`，现有服务 `research-atlas-devstudio-e2e-ejmh`，branch `experiment/devstudio-postgres-e2e-20261114`，隔离测试数据库 `research_atlas_test_db` 的 `atlas_devstudio_e2e_20261114` schema。

## 为什么不直接部署 PR #71

旧 [PR #71](https://github.com/Hu-py/research-opportunity-workbench/pull/71) 基于较早的 Development Studio P0 前端，与已经在 E2E 测试的 V0.4 历史导入、Owner 管理与实验版本化分支不同。因此另建一个以**当前 E2E 分支为基础**的兼容实现，避免覆盖历史实验表、Owner 会话或新版页面。

## 两种同期工作模式

1. **不用 GitHub Actions secrets 的低成本即时模式（测试推荐）：** 启用 `DEVSTUDIO_GITHUB_PUBLIC_POLL_ENABLED=1`。团队 Owner/Admin 打开 `/devstudio/github` 时，FastAPI 在首次读取和每 10 分钟后通过公开 GitHub API 获取最近 20 个默认分支 commits、20 个更新的 PR、20 个 Issues 和最近 20 个 Actions runs。服务端限制频率以降低 GitHub 未认证速率限制；前端每 60 秒刷新 UI，但不会每 60 秒都发起四个 GitHub API 请求。结果持久化在隔离 PostgreSQL schema。**这不是 webhook 即时推送，也不是完整历史回填；首次查看时最多可能有 10 分钟旧的 GitHub 快照。** GitHub API 失败保留数据库旧结果并提示异常，不将缓存数据冒充新实时值。
2. **可选签名 Webhook 推送：** `DEVSTUDIO_GITHUB_SYNC_ENABLED=true` + 后端 `DEVSTUDIO_GITHUB_SYNC_SECRET`（至少 32 字符）；GitHub Actions repo secrets `DEVSTUDIO_SYNC_URL` 指向 **实际 Render Webhook URL**，`DEVSTUDIO_SYNC_SECRET` 与后端一致。这条链路在 webhook 工作流文件进入默认分支、双方 secrets 配齐后才可用。收到 GitHub push、PR、Issue、CI 事件才实时写入。没有配置时完全不影响低成本轮询模式。

后端路径：

- `GET /api/devstudio/github/activity`：复用团队会话权限，返回有来源及时间戳的工程事件和 `public_poll` 状态；
- `POST /api/devstudio/github/webhook`：必须通过 HMAC SHA-256 和完整仓库名校验、幂等 delivery ID；
- `/devstudio/github`：经 Next.js 服务端验证真实 Owner/Admin，再经 `/api/proxy/devstudio/github/activity` 读取数据。只有能访问 Development Studio 的团队成员可进入管理页面。
- `/devstudio`：现有 V0.3 HTML 开发者中心保留，增加“GitHub 动态”入口，不改变原先的页面树和风格。
- 实验 Run：只有已登记的 GitHub Actions run URL 与同步事件匹配时，才更新 `ci_success`/`ci_failure` 状态；**不改变实验结论、科学评分、审核决定、人员权限**。

## 隔离验证与部署门禁

1. 在 GitHub 中对以 E2E 分支为 base 的 PR 进行 Python API 与 Next.js 编译检查。
2. 只将审核后的同步代码合入 E2E 测试分支，绝不自动合入 `main`，绝不替换两个旧 Render API 服务。
3. 在已确认的 Render E2E 服务**仅合并**环境变量 `DEVSTUDIO_GITHUB_PUBLIC_POLL_ENABLED=1`，保持其他 DB/Owner/Token/邮箱隔离设置不变。现有服务 autoDeploy 关闭，所以应在确认 PR/代码后手动触发一次 E2E 部署。
4. 验证 `/api/health`，再由已登录 Owner/Admin 访问 `/devstudio/github`；服务端首次 GitHub 快照保存并显示真实的 PR #57/#58/#69/#70/#71 等**在最近窗口内**的记录，旧记录或未纳入 20 条窗口的事件不应被伪造为已同步。
5. 检查 V0.4 旧实验数量、Owner 会话、待办和审批均仍存在且未变化。公开仓库名称、API 和文献标题不可用于推断私人研究内容。
6. 如 Next.js Preview 因 Vercel 免费额度不可用，则只报告后端成功与 UI 未验证，不称全站已上线。

## 风险与边界

- 公开 GitHub API 默认速率受限；十分钟服务端缓存是一种测试折中，并不保证事件秒级到达。
- 只能同步 GitHub 公开可读取的数据；私有仓库未来需明确新的受限凭据。
- 近期列表不是整个历史仓库数据；追溯全量演化另建按时间游标分页的受控回填。
-  GitHub 工程更新属于 **Development Activity**，不是每个 commit 自动生成 **DevExperiment**。需要科学实验时仍应显式建立假设、基线、输入证据、评价和人工审核。
- Render 测试数据库不可存放真实儿童健康记录或未经授权的团队敏感资料。
