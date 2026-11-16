# Research Atlas V0.5 · 同站开发者中心 V0.3 发布核验

**目标：** 将已确认的统一 HTML V0.3 纳入同一个 Research Atlas 站点，保持原首页两级导航、原有科研前台和业务功能，不另建后台网站。代码在 Draft PR #63，发布前不得把软件 CI 通过当作真实部署。

## 当前实现

- 正式网站：`frontend/public/research-atlas-v0.5.html` 的「研究台 → 管理与设置」新增入口 `/devstudio`。
- 开发者中心：`frontend/app/devstudio/route.ts` 服务端检查真实团队管理员身份；不允许匿名加载。
- UI：获批准的 V0.3 HTML 以服务端模块保存在 `frontend/lib/devstudio-approved-html.ts`，没有直接放到 `public`。动态数据桥接由 `devstudio-live-bridge.ts` 提供。
- 后端：`backend/devstudio.py` 已接入现有 FastAPI，具备问题/变更/审核、文档索引、实验、运行引用和人工评价的持久化接口。
- 四张首页数字卡片可筛选关联模块与右侧待办；历史运行只保存明确关联且未核验的链接。
- 新增来源/文档与审批仅为治理记录；**审批通过不等于 GitHub 合并、生产配置更新或生产生效**。

## 上线前必需检查（发布门禁）

1. **确认生产站点。** Vercel 项目应是 `research-opportunity-workbench`，团队应是当前关联 GitHub 仓库的 Vercel 团队，根目录为 `frontend/`，生产分支 `main`。不要部署到单独 `research-atlas-dev-tracker`。
2. **CI：** PR #63 的最新 Commit 必须通过所有 GitHub 测试，包括 Python 与 Next.js。
3. **Vercel 部署额度：** 2026-11-14 部署请求返回 `402 api-deployments-free-per-day`，需要 Vercel 团队处理配额或等其重置。没有可用的已认证 CLI 作为替代。**尚未进行成功的 Vercel 部署。**
4. **FastAPI 生产服务：** 独立部署新分支后端，检查 `/api/health` 和 `/api/devstudio/overview`。不能假定仅部署 Vercel 就已经使 Python 新端点可用。
5. **数据库：** 生产 PostgreSQL/MySQL 先备份、审查 SQLAlchemy 新表和迁移计划；新表是否已创建由实际部署核查。禁止用无验证的管理台代码直接修改历史生产表。
6. **身份：** `TEAM_AUTH_ENABLED=true` 必须同时在 Next.js 与 API 侧正确配置，确保同一团队会话、API Bearer 凭证和认证代理生效。不要在浏览器或 GitHub 输出密钥。
7. **权限：** 未登录者、普通研究成员访问 `/devstudio` 时必须被拒绝或引导登录；管理员可以登录并查看。如果要让研究成员提交但无法审批，需要下一版设计并实施细分读写权限，目前**开发者中心页面仅授予 admin**。
8. **七页手工回归：** 验证原 Research Atlas 对话/研究台、开发者入口、七页切换、四个 KPI 过滤及重置、期刊申请、文档索引、实验运行登记和独立审批。
9. **生产生效事实：** 通过 CI、通过预览验收、Vercel 部署 READY、FastAPI API 部署更新和数据库迁移成功是**不同的五项验收**；所有步骤确认后才能向团队宣称上线。

## 为什么仍为 Draft PR

Vercel free-team API 在该日期明确返回每日部署配额限制。并且后端独立 API 尚未部署，因此前端就算部署成功，也可能显示“研发 API 暂未连接”的诚实错误状态。为避免误伤正在使用的科研前台，目前保留 Draft 状态，未合并 `main`、未覆盖生产域名。

## 后续功能边界

正式 A/B/C 配置发布、GitHub Run 自动验证、Page 双向正文同步、工作流发布与回滚、部门级开发者权限/复审，都属于独立的后续工程任务。特别是来源表仍需与正在开发的 PR #57 三来源采集器进行安全迁移与实测。
