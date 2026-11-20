# Research Atlas｜研发进度、实验历史与待办快照

**快照日期：2026-11-14。** 本资料是**补录到隔离测试数据库的研发治理快照**，包含已核对的 GitHub PR/CI、Radar A/B 客观采集、产品决策和仍未解决的项目任务。不是单篇论文的科研实验结果，也不是生产站点状态承诺。

## 导入范围

| 类别 | 数量 | 状态解释 |
|---|---:|---|
| 历史研发记录 / 验证工作流 | 11 | 6 待复核、1 进行中、2 受阻、2 待执行 |
| P0 待办 | 4 | 第一批必须推进的开发验收 |
| P1 待办 | 8 | 后续联调、来源和周报链路 |
| P2 待办 | 2 | 正式邮箱和权限治理后续功能 |
| 历史证据事件 | 随记录补录 | 每条写原发生日期和来源链接；数据库写入日期是实际补录日 |

**数据来源**：`backend/fixtures/research_atlas_history_20261114.json`，另有同快照的 `data/devstudio/research_atlas_history_20261114.json` 便于审阅。内容都不包含用户口令、API 密钥和数据库连接串。

## 实验分类、来源与事实边界

| 分类 | 工作流 | 快照阶段 | 可核验事实 | 下一步 |
|---|---|---|---|---|
| DISCOVERY / Radar A | 规划来源与主题采集 | 待复核 | 2026-11-09 JSON：240 篇、16 个候选主题；部分来源 unresolved | 修期刊来源 ID |
| DISCOVERY / Radar B | 计算方法证据采集 | 待复核 | 155 篇、116 摘要、120 PDF、3 代码；部分顶会 unresolved/0 样本 | 核查顶会覆盖度 |
| SIGNAL_L1 | A/B/C 三来源工作流 | 进行中 | Draft PR #57，尚未合并 main | 六个固定任务证据验收 |
| DELIVERY | 数据库周报全链路 | 受阻 | `weekly.yml` 手动触发；另一个公开采集工作流有独立 schedule | 验证 DB 依赖、恢复周报调度 |
| PLATFORM | DeepSeek API 低成本联调 | 待执行 | 需求已明确，尚无完整独立验证结果 | 普通聊天/科研任务双模式 |
| PLATFORM | V0.5 页面设计 | 待复核 | 用户确认黑白极简导航设计；不代表整站功能全部实施 | 逐页代码比对 |
| PLATFORM | Development Studio V0.3 | 待复核 | PR #63 Draft/open，隔离预览曾登录并登记实验 | 七页验收与发布审议 |
| PLATFORM | PostgreSQL E2E | 待复核 | PR #64 Draft/open，隔离日志 PASS_RESTART；浏览器验证过保存与刷新 | 正式库迁移与回归 |
| PLATFORM | Owner 账户 / 邀请 | 受阻 | PR #65 Draft/open；模拟 Owner 可用，真实邮箱未验证 | 正式发信验收暂缓 |
| PLATFORM | 实验管理 V0.4 | 待复核 | PR #67 merged 至隔离分支，CI 通过，测试前后端已发布 | 浏览器完整功能验收 |
| PLATFORM | 群聊 @GPT | 待执行 | 已确定「只在 @GPT/明确点击时调用」的产品规则 | 多人权限/会话联调 |

**“待复核”不是失败，也不是已经科研成功。** 表示存在数据、代码或运行证据，但还没有完成针对该项的人工完整验收。

## 优先推进的 P0

1. 完整跑通 V0.4 的新建、编辑、状态流转、版本历史、刷新持久化。
2. 检查 DevStudio 七页、KPI 小卡筛选、来源提案、文档和审批记录的实际浏览器表现。
3. 核实 Render 免费测试数据库到期时间，制定导出及正式持久化迁移计划；不能把合成账号迁入正式账户库。
4. 审议 PR #63 和 #65 的生产发布门禁，明确团队角色、安全、审批和回滚责任。

## 何处管理

- **实验台账与历史**：新版测试 Preview 的 `/devstudio/experiments`。
- **研发待办**：实验页面顶部「研发待办与问题」，可按 P0/P1/P2、模块和状态过滤；支持「待处理 / 进行中 / 受阻 / 已完成」的人工状态更新，并留审计日志。
- **原有研发总览**：`/devstudio` 的问题与变更模块会读取同一批待办（DevIssue），不维护第二套单独数据。
- **主来源文件**：`backend/fixtures/research_atlas_history_20261114.json`，供重建与追溯，**未来的新实验与修改应通过网页入库**，不要不断靠修改快照覆盖真实数据。

## 入库安全与幂等

新增的 `backend/devstudio_history_import.py` **只**在以下全部成立时执行：

- 显式设置 `DEVSTUDIO_E2E_IMPORT_HISTORY=1` 与 `DEVSTUDIO_E2E_ISOLATED=1`；
- PostgreSQL 数据库名精确为 `research_atlas_test_db`；
- 当前 Schema 精确为 `atlas_devstudio_e2e_20261114`；
- 已启用真实团队会话认证；
- `scripts/devstudio_postgres_e2e.py` 启动脚本完成隔离验证并调用导入。

固定 ID 的实验/待办存在即跳过，**不删除、不覆盖已有用户记录、不会伪造模型调用或实验分数**。历史事件统一标明 `system_backfill_20261114` 和原发生日期，避免误以为由真实 Owner 在过去的日期创建。

**自动测试通过不等于线上数据已导入。** 只有 Render 部署日志出现 `devstudio_history_backfill` 的 `PASS_IMPORTED` / `PASS_EXISTING`，并核验计数后，才可宣布数据库补录成功。

## 后续维护建议

先用网页推进 P0，并逐项补充实际日志、执行人、验收结果、证据和明确的当前状态；再讨论 GitHub PR/CI 状态自动同步。自动同步只能更新经过核对的外部状态，不能擅自将科学结果判为成功。独立的松江儿童健康外推论文、水治理场景、POI 楼层研究不在本次 Research Atlas 开发后台快照中。
