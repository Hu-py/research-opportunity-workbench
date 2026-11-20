# Research Atlas SC02｜个人画像与双主题三探针试运行（2026-11-14）

> **目标：** 以成员本人明确指定的「儿童健康空间外推」「三维竖向城市化」建立独立私有画像，保存两份独立 A/B/C 文献试运行快照到隔离 PostgreSQL，并在原 Research Atlas「研究台 → 知识资产 → 研究画像」打开真实数据页面。

## 已有团队画像

原系统 `backend/profile_intelligence.py` + `backend/profile_database.py` 使用正式团队研究主线、已核验成果、非受限数据目录等数据库来源生成团队画像草稿；`team_profile_revisions` 负责团队正式画像版本。Render 启动日志曾确认 `verified_outputs=36`（不是当前个人论文数量，更不是本人的特定能力证明）。个人画像**不能**改变这些团队来源或审核状态。

## 本版个人画像权限

- 新表 `personal_research_profiles` 以真正登录的 `team_members.id` 为键保存个人明确表达的研究兴趣和研究偏好；`personal_research_results` 以该 member ID 保护结果；`research_pilot_public_evidence` 存公开文章证据快照，不存团队身份。
- 所有 `/api/personal-research/me*` 路由需要有效团队会话、现有服务端 API Bearer。列表和详情按当前 member ID 过滤，其他团队成员猜到结果 ID 也不能访问（404）。
- Owner 可使用 Render **服务端私有环境变量** `PERSONAL_RESEARCH_OWNER_EMAIL` 自动初始化，只有实际登录会话的邮箱与设定邮箱一致且角色为 Owner 才会创建；**不会把邮箱和个人画像写进 GitHub**。
- 其他研究者可明确点击「建立我的画像并载入两个研究结果」，为自己初始化同样的公开证据样本；这是自愿操作，不会自动把某个 Owner 的兴趣传给其他成员。
- 个人画像可以单独编辑；不改变共享研究画像、团队审计的已核验成果或 Research Atlas 日常周报。

## 两个研究结果的真实性与来源

已实际通过网页检索、核对论文出版页；固定为 **研究者辅助文献试运行**，而不是假装 OpenAlex API 或 GPT 后台自主搜索。

| 结果 | 主探针 | 代表性来源 | 最近邻/关键限制 |
|---|---|---|---|
| 儿童健康空间外推 | A: Cities 儿童健康和儿童友好环境；B: CEUS UST-GNN/空间留出研究；C: NeurIPS GraphSAGE + KDD OOD | [UST-GNN](https://doi.org/10.1016/j.compenvurbsys.2026.102466)；[Cities 2026 综述](https://doi.org/10.1016/j.cities.2026.106863) | 道路儿童发育结局与伦敦处方、儿童友好度不同；简单聚合是必备基线 |
| 三维竖向城市化 | A: Cities 竖向可达性/三维扩张；B: EPB 多层连通和 CEUS 建筑图模型；C: NeurIPS GraphSAGE + AAAI SatCLIP | [Vertical 15-minute city](https://doi.org/10.1016/j.cities.2025.106516)；[3D 上海扩张](https://doi.org/10.1016/j.cities.2024.105682) | **最直接近邻** [2026 上海 POI 楼层推断 GraphSAGE–XGBoost](https://doi.org/10.1016/j.jag.2026.105440) 必须单独列作跨刊补充和创新性反证 |

两份快照均有 A/B/C 独立组、每篇原始来源 URL、研究适用限制、一个**待证伪**研究问题和最小验证检查清单。除原始出版摘要外，任何归纳均是**本轮人工辅助研究假设**；`llm_api_executed=false`、`openalex_api_executed=false`、`full_text_audited=false`、`review_status=needs_scientific_review` 字段不得隐藏。

证据不包含原始儿童数据、2022/2026 年 POI 行级数据或未公开论文稿件。引用只记录公开 DOI/出版链接。

## 数据库与初始化

仅在已明确批准的独立 Render 测试数据库 `research_atlas_test_db`、隔离 `atlas_devstudio_e2e_20261114` schema，通过新开关 `PERSONAL_RESEARCH_PILOT_SEED_ENABLED=1` 执行幂等导入：`backend/fixtures/research_atlas_two_domain_probe_review_20261114.json` → `research_pilot_public_evidence` 两行。每行 SHA256 与导入日期保存。文件内容变化时拒绝原位覆盖，要求新版本记录。

真实成员首次打开 `GET /api/personal-research/me`，如果已配置服务端 `PERSONAL_RESEARCH_OWNER_EMAIL` 且其 Owner 登录身份匹配，则只在其 `member_id` 下建立个人画像和两份私有结果副本；不匹配时保持空白并可点击 `POST /api/personal-research/me/initialize`（主动个人初始化）。

## 前端加载

- 访问 `/research-atlas-v0.5.html?space=research&module=knowledge` →「研究画像」→「个人画像」→「查看我的画像与两个研究结果」。
- 页面 `/research/personal` 通过 Next.js 服务端先验证真实团队登录，再从 `/api/proxy/personal-research/me` 与 `.../me/results` 获取数据库内容，而不是前端使用固定虚假数据。
- 页面包含两个可切换主题、各自三探针论文、跨刊近邻、待验证科研问题、原始来源和证据指纹，供本人编辑偏好；无登录者被拒绝。
- 未完成 GitHub 自动部署不应声称网页已上线；Render 后端成功不等于 Vercel 新路由已可访问。

## 验收

```bash
python -m pytest -q tests/test_personal_research_sc02.py
python -m pytest -q
cd frontend && npm run build
```

在隔离环境部署后，确认启动日志 `sc02_public_research_evidence_import: {available:2}`，用真实Owner会话确认 `/api/personal-research/me/results` 恰好两条，其他成员看不到该账号的个人画像，刷新和再次登录不重复插入。此版本没有付费模型执行；未来真正 Agent 自动扫描需要新的可审查 Run 并独立版本化。
