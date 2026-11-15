# SC03 · 儿童健康外推：按任务自动发现新期刊与人工审批 V0.1

## 当前问题与约束

Research Atlas 的全局 `research_sources` 已列入不少规划、GIS、计算机期刊与会议，但此前仅围绕 A/B/C 的固定候选范围执行部分测试；既有模型检索仅能使用 **enabled + 已解析精确 OpenAlex Source ID** 的来源。对于儿童健康空间外推，这可能忽略 `Environmental Research`、`Health & Place`、`Environment International`、`Social Science & Medicine` 等跨学科期刊。

**这些名字只是建议关注的候选领域，并不是已经按实际检索证据批准的新增目录项。不得在没有 OpenAlex 证据与用户审批时自动加到正式筛选范围。**

## V0.1 实现范围

独立任务：`child_health_extrapolation`，中文「儿童健康空间外推」，归属真实登录的 `team_members.id`。不扩展三维城市化、不覆盖团队全局来源配置。

| 功能 | 本版实现 | 边界 |
| --- | --- | --- |
| 任务初始期刊 | 3 个探针 × 3 个已整理的基线期刊 | 与全球大目录区分；未解析来源只显示，不参与严格 Source ID 检索 |
| 发现新期刊 | 实际向 OpenAlex Works 进行 6 条搜索，每条最多 40 条结果；按 `primary_location.source.id` 聚合 | 直接基于**论文的原始期刊身份**；不调用 LLM；不会从期刊名称凭空推测 |
| 候选证据 | 保存 OpenAlex Source ID、ISSN-L（如有）、出现次数、涉及检索词、最多 4 篇原论文链接、查询计划版本 | 检索命中率 ≠ 期刊质量、影响因子、学术排名，也不代表相关论文已人工精读 |
| 候选去重 | 一个 OpenAlex Source ID 对应一个任务候选，保留相关的 A/B/C 探针；已审核候选不可重新静默覆盖 | 同一篇论文可能跨查询命中，按 Work ID 去重 |
| 审批 | 本人查看论文证据，填写理由，批准或拒绝 | 只有本人可批准本人任务的**系统发现**候选；操作记录团队审计，但私人内容不公开 |
| 任务目录 | 审批后写入隔离表 `task_venue_directory`；可暂停 / 恢复 | 不修改 `research_sources`、团队正式画像、其他人或其他任务 |
| 目录检索测试 | 使用已解析基线期刊与已批准期刊的 OpenAlex Source ID 冻结为快照，严格做论文检索 | Source ID 为空时拒绝，不能偷偷退化为无来源限制的全网搜索；无 LLM 总结 |
| API 调用预算 | 单次六个工作搜索查询；每次最多 40 条；5 分钟请求间隔 | OpenAlex 搜索按服务的当前资费或配额计费（估算六次查询的基础搜索费约 $0.006，若用免费额度则无额外账单）；付费账号/配额由 OpenAlex 决定，不能保证免费 |

### 相关数据表

- `task_venue_discovery_runs`：请求、执行、查询数、检索量、错误、时间和计划版本
- `task_venue_candidates`：未经批准的候选来源、原论文证据、审核状态和责任人
- `task_venue_directory`：真正批准生效的任务目录项、状态和审核记录
- `task_venue_paper_runs`：严格限定来源扫描的冻结输入和检索结果

这四个新表使用当前隔离测试 PostgreSQL，不进行现有历史表重构；数据库建表前通过 `backend.api` 注册 ORM。每次写入同时记录审计事件。

### REST 与前端

`GET /api/personal-research/me/journal-radar` 读取本人任务基线、候选、运行、获批目录、可用 source id 和扫描论文。

`POST /api/personal-research/me/journal-radar/discover` 创建单次、显式启动的搜索。任务在 FastAPI BackgroundTasks 中执行，测试机可能睡眠/重启；因此成功、失败和部分成功状态必须真正落库。

`POST /api/personal-research/me/journal-radar/candidates/{candidate_id}/review`，body `{"decision":"approve"|"reject","reason":"..."}`，仅限本人候选，终态不能重复审批。

`POST /api/personal-research/me/journal-radar/directory/{id}/status` 暂停或恢复。

`POST /api/personal-research/me/journal-radar/scan-approved` 使用**已经批准的 Source ID**和已精确解析的初始来源搜索，不执行 LLM。

前端：`/research/personal` → 「儿童健康空间外推」→ 「打开期刊智能发现与审批」→ `/research/personal/journals`，和之前的 Research Atlas 黑白极简风格保持一致。

## 为什么这一步不是简单修改 Skill？

本轮主要修复检索的**来源选择与人工治理**，不是简单告诉 LLM「多找几个期刊」。属于数据库目录、检索执行器、审批 UI、证据存储与测试，随后才把它作为 Discovery Skill 的工具接口。

将来支持多个研究方向时，可将 `TASK_KEY` 和查询模板抽象成用户可管理的参数；本期**只实现一个任务**，避免过早泛化导致规则难以测试。

## 这轮研究质量如何评价？

建议人类审核者给每本候选记录：
- 是否与儿童健康空间外推有关（有论文证据）；
- 提供的论文是否属于有意义的研究而不是泛化命中；
- 与现有期刊目录是否互补（规划、城市科学、儿童健康、计算方法）；
- 是否值得纳入当前任务持续监测，而不是将其评价为普遍意义上的“好期刊”。

批准的期刊才进入任务目录。然后严格扫描并比较扩容前后检索到的论文是否在**相关性、独立性、研究深度与新方法价值**上有所增益。不能仅比较「论文数量变多了」。

## E2E 验收标准

1. 两个登录成员各自看到 9 条初始基线，候选队列独立。
2. Mock OpenAlex 六条查询产生 3 组候选；不允许自动批准、伪造期刊质量评级。
3. 同一个候选必须按本人身份明确填写理由批准，其他人的操作 404。
4. 已批准 Source ID 可以进入本任务 strict source filter；未批准的候选绝不会影响检索。
5. 暂停后该 Source ID 即时从可用列表消失，恢复后加入。
6. 完成一次真实 OpenAlex 检索后检查每项来源链接与 DOI 原论文证据，报告失败的查询而不伪造论文。
7. Render E2E 和 Vercel Preview 分别验证；不操作正式 main/production、不使用未经授权的真实儿童健康数据。

## 未实现

- 本版不做模型训练、自动 LLM 科研周报或论文全文验证。
- 不做期刊影响因子/分区判定（需要独立合法数据源与实际年份）。
- 不做跨用户团队共同目录合并，因为需要独立审批角色与共享边界。
- 不自动把 DevStudio Change 的“批准”视作全局 Registry 已生效。本轮采用专门的**个人任务期刊目录**生效机制，避免旧 Change 自审批与申请者一致的治理冲突。
