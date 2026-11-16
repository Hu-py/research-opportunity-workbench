# SC05 · ChatGPT 完整科研工作流操作指南

> 目标：直接在 ChatGPT 中创建、运行、追踪、盲评和分析一整组 SC05 A/B 实验。  
> 本文是操作指南；部署状态必须以 Render live commit 和 ChatGPT 当前 MCP 工具清单为准。

## 1. 先区分四种状态

| 状态 | 意义 |
|---|---|
| 代码已实现 | GitHub 分支存在 MCP 工具和实验逻辑 |
| CI 通过 | 自动化测试和前端构建通过 |
| Render 已部署 | 隔离 Render 服务正在运行对应 commit |
| ChatGPT 已连接 | OAuth 授权完成，ChatGPT 实际发现当前工具清单 |

只有最后两项也通过，才能在 ChatGPT 里完成真实端到端实验。CI 的 mock LLM 结果不是真实 DeepSeek 结果，也不是科研质量证明。

## 2. ChatGPT 可用工具

当前 MCP 设计包含以下工具：

| 工具 | 用途 | 是否会调用模型 |
|---|---|---|
| `list_experiments` | 列出 Owner 论文、实验、轮次和预算 | 否 |
| `create_paper_case` | 用提取后的 Methods/Results 页面文本创建私人论文案例 | 否 |
| `create_ab_pair` | 创建 gate-off / gate-on 两组实验 | 否 |
| `prepare_experiment` | 单个 Run 的检查点和预算预检 | 否 |
| `prepare_ab_pair` | 对整组 A/B 做成对预检 | 否 |
| `get_executor_status` | 检查 PostgreSQL probe、队列和执行器开关 | 否 |
| `get_experiment_status` | 读取单个 Run 状态和检查点数 | 否 |
| `get_experiment_result` | 读取已完成 Run 报告和质量指标 | 否 |
| `get_ab_pair_status` | 读取 A/B 阶段并同步轮次台账 | 否 |
| `start_ab_pair` | 顺序启动下一组可执行的 A/B arm | **是，可能产生费用** |
| `start_experiment` | 单个 Run 的兼容启动/恢复入口 | **是，可能产生费用** |
| `get_ab_pair_result` | 读取匿名 A/B 报告 | 否 |
| `record_blind_review` | 保存匿名 A/B 的盲评评分 | 否 |
| `compare_ab_pair` | 两组盲评完成后解盲比较 | 否 |
| `list_experiment_rounds` | 查看持久化实验轮次台账 | 否 |
| `record_experiment_round` | 创建或更新实验轮次记录 | 否 |

读操作使用 `experiments:read`。创建案例、创建 A/B、启动、更新轮次、盲评和解盲需要 `experiments:run`。工具注册的权限声明必须与实际副作用一致。

## 3. 从论文到 A/B 的完整流程

### Step 0 · 检查执行器和历史状态

先调用：

- `get_executor_status`
- `list_experiments`

核对当前 Owner、历史论文案例、正在执行的任务、剩余预算、队列状态和已有失败检查点。不要因为看到旧的 `queued` 或 `failed` 状态就直接重跑。

### Step 1 · 创建论文案例

如果论文案例已经存在，直接使用其 case ID。

如果需要在 ChatGPT 内创建：

1. 将论文 PDF 上传到 ChatGPT。
2. 从论文中提取适合盲测的 Methods / Results 页面内容。
3. 使用 `create_paper_case` 保存标题和 `page_01`、`page_02` 等页面文本。
4. 工具会应用与 PDF 上传相同的盲测过滤规则，计算来源 SHA-256，并保存到 PostgreSQL。

该 MCP 文本入口每次请求最多接收 **48,000 字节的 UTF-8 JSON 负载**（中文字符会占用多个字节）。更长的 PDF 使用已认证的 Research Atlas PDF 上传页面；不要把私有 PDF 提交到 GitHub。

创建案例不调用 DeepSeek，也不产生模型费用。

### Step 2 · 创建干净 A/B 配对

调用 `create_ab_pair`：

- `case_id`：已登记的论文案例 ID。
- `confirm_create=true`：确认创建记录。
- `fresh_copy=true`：当旧案例可能含有历史共享证据时，复制同一来源快照并清空共享证据；新建的干净案例可不复制。

系统创建两组：

- A / baseline：`science_gate_off`
- B / treatment：`science_gate_on`

创建配对不会调用模型。

### Step 3 · 登记实验轮次

调用 `record_experiment_round`，记录：

- 轮次编号，例如 `R6.3`
- 实验类别
- 待解决问题
- 方法
- 实验内容
- pair ID
- 详细记录

默认类别：

| 类别 | 含义 |
|---|---|
| ◆01 | 工作流完整性 |
| ●02 | 科学质量 |
| ▲03 | 证据与文献关联 |
| ■04 | 创新性与研究路线 |
| ◇05 | 执行稳定性与成本 |

轮次台账保存在 PostgreSQL，不依赖当前聊天窗口。

### Step 4 · 成对预检

调用 `prepare_ab_pair`，确认：

- 两组使用相同来源 SHA-256；
- 两组 pipeline SHA 一致且与当前版本一致；
- baseline 尚未完成时，gate-on 不允许启动；
- baseline 完成后共享证据已经冻结；
- 没有并发 Run；
- 当前执行器和预算允许继续。

预检不调用 DeepSeek。

### Step 5 · 顺序启动

调用 `start_ab_pair`，明确设置 `confirm_paid=true`。

它只启动下一组安全的 arm：

1. 第一次启动 gate-off baseline。
2. baseline 完成并冻结证据后，再调用一次，启动 gate-on。
3. 不会同时启动两组，也不会自动重复已经完成的付费请求。

**`confirm_paid=true` 只能在用户明确同意实际 DeepSeek 模型调用及可能产生的费用后使用。** 服务器端还必须打开相应付费开关，并确认队列消费者可用。

### Step 6 · 追踪执行

调用 `get_ab_pair_status`，读取：

- 当前阶段；
- 两组状态；
- 已保存检查点；
- 模型调用数和 token；
- 错误与恢复预检；
- 下一步安全动作。

该工具会同步轮次台账，因此需要 `experiments:run` 权限。它不调用模型。

### Step 7 · 盲评和解盲

两组均完成后：

1. 调用 `get_ab_pair_result`，获取匿名 A/B 报告。
2. 对 A 和 B 分别调用 `record_blind_review`。
3. 评分维度为准确性、科学价值、叙事机制、文献深度、可行性，均为 0–5 分。
4. 两组盲评保存后，调用 `compare_ab_pair` 解盲。
5. 系统记录分数差异、科学价值差异、质量警告和模型使用量。

加权评分为：准确性 15%、科学价值 30%、叙事机制 25%、文献深度 20%、可行性 10%。硬失败会将总分归零。评分是研究者评价证据，不等于科学正确性证明。

### Step 8 · 更新实验台账

调用 `list_experiment_rounds`，核对：

- 待解决问题
- 方法
- 实验内容
- 状态
- 简要结果
- 后续
- 详细记录
- 来源和 pipeline 哈希

完成解盲后，再依据真实结果决定下一轮修复点；不要把一次 A/B 的分数直接外推为跨论文泛化结论。

## 4. 云端执行与安全限制

- PostgreSQL 是运行状态、检查点、审计和轮次台账的权威记录。
- R2 是可选私有归档；R2 失败不能触发重复的付费模型请求。
- Render free Web Service 可能休眠或重启。Inline worker 不是高可用独立 Worker。
- 当前 Render workspace 没有已确认的独立 SC05 Background Worker 资源；在确认实际执行器状态前，不得打开付费启动。
- `claimed` / `running` 中断任务不会自动偷取或重放，避免重复扣费；必须先检查保存检查点。
- API Bearer Token、Owner 密码、DeepSeek Key、PostgreSQL URL、R2 密钥不得粘贴到 ChatGPT 或提交 GitHub。

## 5. 当前发布状态与验收要求

本轮工具与轮次逻辑已写入独立整理分支。Render 隔离服务配置为手动部署，因此 GitHub commit 不会自动更新 Render。必须依次完成：

1. 当前分支 CI 全部通过。
2. 将经过审查的代码合并到 Render 绑定的 staging 分支。
3. 手动部署并核对 Render live commit。
4. 检查 `/api/health`、OAuth discovery、无授权 MCP challenge。
5. 在 ChatGPT 重新授权 `experiments:read experiments:run`，确认工具清单包含上述工具。
6. 先完成只读检查、文本案例创建、A/B 创建和成对预检。
7. 只有在用户明确同意费用且执行器已验证时，才做真实模型运行。
8. 完成匿名报告、盲评、解盲和 PostgreSQL 轮次记录回读。

**最终验收不是“代码已提交”，而是 ChatGPT 实际完成一次可追溯的 A/B 全流程。**
