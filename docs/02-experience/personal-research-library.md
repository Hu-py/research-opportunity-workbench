# Research Atlas · 个人科研资料库与动态画像

**状态：** Backend deployed to Render test API; frontend merged pending production deployment  
**数据边界：** 所有个人资料以当前认证的 \`team_members.id\` 为所有者，与团队共享画像隔离。

## 1. 设计原则

个人研究画像与个人科研资料是两种不同对象：

- **个人研究画像**：研究目标、研究主线、核心问题、关键词、问题检索词、方法检索词。
- **个人科研资料库**：论文、智能体报告、实验结果、项目、数据集和研究笔记。
- **关系**：一条资料可以关联一条或多条个人研究主线；一条主线也可以关联多份资料。

新增论文、报告或实验结果属于数据操作，不需要重新部署前端。只有新增交互、页面或业务能力时才需要部署代码。

## 2. 数据库结构

### \`personal_research_profiles\`

每个成员一条当前画像记录：

- \`member_id\`：关联 \`team_members.id\`，主键。
- \`profile_json\`：当前个人研究主线与检索画像。
- \`version\`：乐观并发版本。
- \`created_at / updated_at\`：时间戳。

### \`personal_research_profile_revisions\`

个人画像版本历史，按 \`member_id + version\` 唯一。

### \`personal_research_assets\`

个人科研资料主表：

- \`id\`：资料 UUID。
- \`member_id\`：资料所有者。
- \`client_key\`：客户端幂等标识。
- \`kind\`：publication / agent_report / experiment_result / project / dataset / note。
- \`title / summary\`：标题和摘要/结果说明。
- \`url\`：原始资料链接（如有）。
- \`source_type / source_id\`：来源类型与来源记录 ID。
- \`metadata_json\`：DOI、期刊、实验指标、运行状态、版本等结构化元数据。
- \`status / archived_at\`：软归档状态。
- \`created_at / updated_at\`：时间戳。

### \`personal_research_asset_lines\`

资料与个人研究主线的多对多关联。移除研究主线时只解除关联，不删除原资料。

## 3. API

全部个人资料接口要求有效团队成员会话，并且服务端从会话解析 owner ID；客户端不能指定或伪造 \`member_id\`。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | \`/api/personal-profile\` | 读取当前账号画像 |
| PUT | \`/api/personal-profile\` | 版本化保存画像；首次保存时将初始论文/报告证据原子写入资料库 |
| GET | \`/api/personal-assets\` | 查询当前账号资料，支持 \`kind\`、\`line_id\`、\`q\`、\`include_archived\` |
| POST | \`/api/personal-assets\` | 新增/幂等更新资料 |
| PUT | \`/api/personal-assets/{id}\` | 修改本人资料 |
| DELETE | \`/api/personal-assets/{id}\` | 软归档本人资料 |
| POST | \`/api/personal-assets/import-paper\` | 从共享 \`papers\` 表按 DOI 或 Paper ID 导入个人引用 |
| POST | \`/api/personal-assets/import-task\` | 将已有 Research Atlas 任务结果快照导入个人资料库 |

## 4. 来源类型

- \`doi\` / \`openalex_work\`：学术论文。
- \`chatgpt_space_page\`：ChatGPT Space 原始报告页。
- \`research_task\`：Research Atlas 内部任务报告。
- \`sc05_run\`：SC05 实验运行 ID。
- \`library_file\`：个人 Library 文件引用。
- \`external_url\` / \`manual\`：其他外部链接或手动资料。

当前可直接从共享 Paper 表和 ResearchTask 表导入；SC05 外部运行先通过 Run ID、摘要和结构化元数据登记引用，后续可增加 SC05 数据源连接器自动同步。此时不会伪称已读取外部实验数据库。

## 5. 文件与大对象

个人资料库只保存元数据和来源引用，不把 PDF 二进制内容塞入 PostgreSQL：

- PDF 原文继续保存在 ChatGPT Library 或对象存储。
- 资料表记录 DOI、URL、Library file reference 或外部存储键。
- 后续可增加 R2 文件对象与个人资料的绑定 API。

## 6. 隐私与审计

- 所有读写查询都附带当前认证成员 ID。
- 不允许通过请求参数传入另一个成员 ID。
- 其他成员即使猜到 asset UUID，也只能得到 404。
- 画像和资料写入团队审计表时只记录操作类型、对象 ID 和类别，不把完整私人研究内容写入团队审计日志。
- 归档是软删除；原始论文、团队任务和实验记录不会被删除。
- \`/api/profile\` 继续是团队共享画像，与个人画像接口分离。

## 7. 何时需要重新部署

| 操作 | 是否需要部署 |
| --- | --- |
| 新增论文、报告、实验结果 | 否 |
| 修改资料标题、摘要、DOI、链接或元数据 | 否 |
| 将资料关联到另一条个人主线 | 否 |
| 归档资料 | 否 |
| 新增资料类型、导入器或新交互 | 是 |
| 新增数据库字段或 API 行为 | 是 |

