# Research Atlas 前端设计与产品范围变更记录

## 个人资料库前端合并与发布门槛 — 2026-11-23

- Personal Research Library 前端 PR #139 已合并至 `main`（commit `4bba4374`），GitHub CI 通过。
- Vercel 生产发布工作流已从 `main` 触发，但在凭证预检阶段停止：GitHub Actions 仓库缺少 `VERCEL_TOKEN` Secret。没有开始 Vercel link/pull/build/deploy，正式域名仍指向旧前端。
- 只需由仓库所有者在 GitHub Settings → Secrets and variables → Actions 添加 `VERCEL_TOKEN`（Vercel team token），然后重新运行 `Deploy Research Atlas to Vercel Production` 工作流。
- Token 不应通过聊天发送；前端发布后，用户登录自己的团队成员账号，进入「研究设置 → 研究画像」，检查三条预填主线并点击「保存到我的账号」，初始 Shen 论文与 R6.4.5 报告会随画像保存自动进入个人科研资料库。

## 个人科研资料库 — 2026-11-23

- 后端 PR #138 已合并至 Render API 分支，Render `research-atlas-api-test` 已部署 commit `3875aaf`；新增 `personal_research_assets` 与 `personal_research_asset_lines`，并提供个人资料 CRUD、论文/任务导入接口。
- 个人画像首次保存会将 Shen et al. TRD 论文和 R6.4.5 原始/综合报告作为独立资料记录写入个人资料库，不再把资料清单作为画像 JSON 的唯一存储。
- 新增 Personal Research Library 前端组件：动态读取资料、按类型筛选、新增/编辑/归档、关联多条研究主线、导入共享文献和 Research Atlas 任务。
- 实验结果支持 `sc05_run` 来源 ID 与结构化 JSON 元数据；当前外部 SC05 数据源尚未自动连接，需通过新增资料登记引用和结果摘要。
- 所有资料按认证成员 ID 隔离；归档不删除原文或团队任务；移除研究主线只解除资料关联。
- Vercel CLI 发布工作流已加入，但运行检查发现 GitHub Actions 尚未配置 `VERCEL_TOKEN` Secret。添加该 Secret 后可运行正式部署；不需要把 Token 发到聊天中。
- 动态资料新增、修改和归档不需要重新部署前端；新增界面或 API 能力才需要部署。

## 个人研究画像接入记录 — 2026-11-23

- 后端 PR #132 已合并至 Render API 分支 `feat/shared-team-workspace`，Render `research-atlas-api-test` 已部署 commit `bc9596c`。
- 新增成员级 `personal_research_profiles` 与版本历史表，按已认证的 `team_members.id` 隔离；新增 `GET/PUT /api/personal-profile`。原团队共享 `/api/profile` 不变。
- 前端 PR #134 已合并至 `main`（commit `c04f8fd`），GitHub CI 通过；设置页新增三条个人研究主线预填、论文/报告链接、编辑与版本化保存。
- Vercel 正式部署本次被 Hobby 每日 API 部署限额（HTTP 402，超过 100 次）阻挡；生产域名仍为旧前端版本。不要直接提升 Preview，也不要更改计费/安全设置。
- **数据状态：** 三条主线当前是前端预填草稿，尚未写入任何成员数据库行。正式前端部署后，用户登录自己的账号，在「研究设置 → 研究画像」检查并点击「保存到我的账号」，才会写入该账号的个人画像表。不会自动写入团队画像。

## V1.0 发布部署记录 — 2026-11-23

- 前端产品范围与任务专属 A/B/C 期刊配置已合并至 `main`（commit `7b1772d`）。
- 后端来源配置接口已部署至 Render `research-atlas-api-test`（commit `8d0b26d`），继续使用测试数据库 `research_atlas_test_db`。
- 本次发布不切换数据库、不重建现有数据。
- Vercel 正式发布尚未完成：Hobby 每日 API 部署额度（超过 100 次）返回 402，需等待 24 小时配额恢复或由项目所有者在 Vercel 端解决额度限制。Git 主分支更新未产生新的 Vercel 部署；当前正式域名仍指向旧部署。
- 不直接提升 Preview 部署，因为 Preview 环境缺少 Production 专用的定时任务密钥。

## V1.0 来源配置补充 — 2026-11-22

**恢复专属清单：** 来源总目录与任务使用范围分离；SC01 团队周报、SC02 个人周报、SC03 定向科研任务分别管理 A/B/C 来源。定向任务支持单次来源覆盖和快照；严格模式未核验来源不能自动扩大检索范围。详见 [任务专属来源设计](task-specific-source-scopes.md)。

## V1.0 — 2026-11-22 · 当前产品范围基线

**产品定位：** 面向团队与个人的跨学科科研发现和研究辅助平台。

**一级导航：** 只保留「对话」与「研究台」。

**对话：** 私人对话、团队对话、GPT 调用、深度研究。

**研究台：** 团队周报、个人周报、定向科研任务、研究设置。

**底层共用能力：** 文献发现与证据整理、科研问题与方法分析、创新性/可行性/证据审查、团队与个人画像匹配、报告/引用/反馈/运行记录。上述能力不单独做菜单。

**研发管理：** Development Studio、A/B 实验、版本管理和研发审批独立于普通用户端。

**范围收敛：** 不再为论文库、知识图谱、机会池、选题演化、Agent 任务台、AI 选题实验台、博弈回放、团队成果、数据台账和统计大屏设置普通用户端独立入口。

**版本关系：** V0.5 的黑白极简视觉和双一级导航继续沿用；V0.5 四个研究台模块退为历史设计，不再代表当前产品范围。

## V0.5 — 2026-11-14 · 历史视觉与交互基线

**视觉：** 黑白灰极简，弱化装饰与仪表盘感。

**导航：** 全球一级入口收敛为「对话／研究台」；二级侧栏按一级入口动态切换。

**主页：** 对话默认入口；无 Slogan、Hero 和架构总览。

**画像：** 团队正式画像／个人私有画像共存，权限语义分离。

V0.5 是 UX 设计版本，不代表所有静态演示模块都属于当前产品功能。
