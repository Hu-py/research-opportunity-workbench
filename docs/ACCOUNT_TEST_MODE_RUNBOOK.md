# Research Atlas · 无域名模拟邮箱测试（仅隔离环境）

> 仅用于 Render 服务 `research-atlas-devstudio-e2e-ejmh` + Vercel Preview 分支 `experiment/devstudio-postgres-e2e-20261114`。
> **无真实邮箱验证、无真实邮件发送、不可证明任何 QQ 邮箱所有权、不可合并进正式版本。**

## 测试 Owner 身份

使用 `owner-sandbox@research-atlas.invalid`。不要将 `2265176686@qq.com` 用于模拟发信或激活真实 Owner。该真实邮箱仅留在 PR #65 的正式邮箱验证流程中，待以后启用真实邮箱供应商。

## 严格隔离条件

1. E2E 启动器先验证 `DATABASE_URL` 仅指向 `research_atlas_test_db`，并把 PostgreSQL `search_path` 设置为 `atlas_devstudio_e2e_20261114`。
2. `ACCOUNT_EMAIL_MODE=preview_inbox`、`DEVSTUDIO_E2E_ISOLATED=1` 且 `TEAM_OWNER_EMAIL=owner-sandbox@research-atlas.invalid` 同时成立。
3. 测试收件箱中的验证链接仅保存在运行进程内存中；只接受 `@research-atlas.invalid` 收件人。所有非测试域名会被发送函数拒绝。
4. `/api/account/test-inbox` 必须带服务端 Bearer 和已登录 Admin/Owner 会话；前端 `/account/test-inbox` 只在 Vercel **preview** 且后端等于指定 Render E2E 服务时可访问。
5. 新增账户和邀请数据只写隔离 Schema，绝不把这套测试 Owner 当作真实邮箱 Owner。

## 必需的 Render 环境变量（在 Render Dashboard 中配置）

- `DEVSTUDIO_E2E_ISOLATED=1`（现有）
- `ACCOUNT_EMAIL_MODE=preview_inbox`
- `TEAM_OWNER_SETUP_ENABLED=true`
- `TEAM_OWNER_EMAIL=owner-sandbox@research-atlas.invalid`
- `PUBLIC_APP_URL=https://<本次 Vercel Preview 部署域名>`（必须是 HTTPS 的 `.vercel.app` 域名）
- `SMTP_HOST=test-inbox.invalid` 和 `SMTP_FROM=simulated@research-atlas.invalid`：**仅用于通过邮件模块预检，启动器会用模拟发件函数替换实际传输；绝不连接此 SMTP 地址。**

这些变量只增加到隔离 E2E 服务，不能写入现有两个后端、Production、GitHub Actions Secrets 或公开文档的真实域名密钥中。

## 浏览器手工验收流程

1. 管理员用现有隔离测试账号登录 `/devstudio`（该账号已在此前 E2E 测试创建）。
2. 在同一 Vercel Preview 域名访问 `/account/setup`，输入 `owner-sandbox@research-atlas.invalid`，申请模拟验证。
3. 返回 `/account/test-inbox`，刷新并打开最新 Owner 模拟验证链接。
4. 自行设置一条新的测试密码（不要发送给 ChatGPT），完成后用测试 Owner 邮箱登录 `/devstudio`；确认角色为 Owner。
5. 进入 `/account/team`，邀请 `researcher-sandbox@research-atlas.invalid`，在模拟收件箱领取链接，设置密码并验证 Researcher 登录与权限。
6. 检查重复领取、撤销邀请、角色修改和审计。记录各环节响应；**不使用真实邮箱，不向真实团队成员发信**。

## 退出测试模式

- 关闭 `ACCOUNT_EMAIL_MODE`、`TEAM_OWNER_SETUP_ENABLED`，停止或销毁隔离测试服务中的测试邮箱功能；数据库中的模拟账号按测试数据保留或依法清理。
- 正式系统只能启用 PR #65 的**真实邮件交付**与邮箱验证，重新部署到独立生产数据库，并用 Owner 的真实邮箱重新认领。
- 文档、截图、汇报应写“模拟邮箱联调通过”，不能写“邮箱验证已通过”或“真实 Owner 已激活”。
