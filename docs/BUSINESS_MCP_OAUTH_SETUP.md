# Business Workspace Agent — MCP OAuth 接入与权限配置

> 当前生产路径：Render FastAPI MCP + Supabase OAuth Server  
> 目标 MCP 地址：`https://research-atlas-api-test.onrender.com/research-advisor/mcp`  
> 日期：2026-11-08

## 1. 唯一正式 MCP 路径

本项目正式采用 Render 上的 FastAPI MCP adapter：

- MCP endpoint：`https://research-atlas-api-test.onrender.com/research-advisor/mcp`
- OAuth consent 页面：`https://research-atlas-api-test.onrender.com/oauth/consent`
- MCP 实现：`backend/business_mcp.py`
- Consent 页面：`backend/oauth_consent.py`
- 数据库：Supabase PostgreSQL。

**暂不部署** `supabase/functions/research-advisor-mcp` 原型。该 Edge Function 是独立只读原型，当前工具集不完整；不要同时把它和 Render MCP 接入同一个 Workspace Agent，以免形成两套授权和数据写入路径。

Render 不是数据库必需品，但当前 Python 多 Agent 选题引擎和 MCP 服务均在 Render。现阶段保留 Render 作为执行层，Supabase 仍是唯一长期数据源。

## 2. 当前状态

- Supabase OAuth Server 已在项目中启用。
- Render 服务当前分支为 `feat/shared-team-workspace`，自动部署关闭。
- Render 已部署包含独立 consent 页面和 MCP adapter 的代码。
- MCP 默认关闭；真实浏览器 OAuth PKCE 握手、ChatGPT Business 连接和完整读写回环尚未完成。
- 不要因为代码已部署就宣称 Workspace Agent 已连接。
- Vercel 不是第一阶段 OAuth 连接的依赖。

Consent 页面使用 Supabase browser OAuth APIs 和 public publishable key，只负责用户认证及批准/拒绝授权，不读取团队研究数据库。

## 3. Supabase OAuth 配置

Supabase issuer：

`https://tfyfupxabojddixwjkat.supabase.co/auth/v1`

JWKS：

`https://tfyfupxabojddixwjkat.supabase.co/auth/v1/.well-known/jwks.json`

OAuth authorization-server discovery：

`https://tfyfupxabojddixwjkat.supabase.co/.well-known/oauth-authorization-server/auth/v1`

OIDC discovery：

`https://tfyfupxabojddixwjkat.supabase.co/auth/v1/.well-known/openid-configuration`

**JWT Signing Key 必须使用非对称算法。** 当前 Render verifier 只接受 `RS256` 或 `ES256`，并通过同一 Supabase 项目的 JWKS 公钥验证签名。Supabase 新项目默认可能使用 `HS256`；如果当前项目仍是 HS256，OAuth MCP 连接会被拒绝。请先在 Supabase JWT Signing Keys 设置中确认并迁移到 RS256/ES256，再验证 JWKS 中存在对应公钥。不要把 Supabase JWT secret 或私钥复制到 Render。

Render consent 页所需公开配置：

- `OAUTH_CONSENT_ENABLED=true`
- `OAUTH_CONSENT_SUPABASE_URL=https://tfyfupxabojddixwjkat.supabase.co`
- `OAUTH_CONSENT_PUBLISHABLE_KEY=sb_publishable_...`

只使用 Supabase Publishable Key。**禁止**把 service-role key、数据库 URL、DeepSeek Key 或 OAuth token 放入浏览器、GitHub、Workspace Agent 指令或 Skill。

Supabase Dashboard → Authentication → URL Configuration：

- Site URL 应在确认 Render consent 页面可访问后设置为 `https://research-atlas-api-test.onrender.com`。
- Redirect allow list 应包含 `https://research-atlas-api-test.onrender.com/oauth/consent`。
- OAuth Server Authorization Path：`/oauth/consent`。

在真实浏览器访问 consent 页面并确认登录/批准/拒绝流程之前，不要更改 Site URL。当前外部浏览器连通性尚未由本项目自动化验证。

### Supabase 用户身份与 ChatGPT OAuth client

原 Research Atlas 团队登录与 Supabase Auth 登录是两套身份。必须先创建或确认 Supabase Auth 用户，再由管理员批准具体 Supabase user UUID。

Supabase OAuth Server 支持 MCP 兼容客户端的动态注册，也支持授权码 + PKCE 和 refresh-token grant。首次接入时，优先按 ChatGPT 的 OAuth discovery / client-registration 流程测试；只在 consent 页面已验证、Owner 批准后启用所需的动态注册能力，并记录实际生成的 client ID，再加入 Render allowlist。不要使用通配符 client allowlist。

**Refresh-token 兼容性需要实测。** Supabase OAuth Server 支持 refresh-token grant，但其当前公开文档列出的标准 scope 为 `openid`、`email`、`profile`、`phone`，没有明确列出 `offline_access`；ChatGPT 自定义 MCP OAuth 文档建议 OIDC 提供方支持 refresh token，并通常通过 `offline_access` 请求。首次连接必须确认 ChatGPT 的实际授权请求和 Supabase discovery 是否兼容。如果 ChatGPT 请求 `offline_access` 而 Supabase 拒绝，先停止发布，不要通过放宽 JWT 校验解决；应评估兼容的 OAuth adapter 或其他标准 OIDC provider。

Supabase OAuth 的标准 scope 不会自动授予本项目的科研权限。服务器不信任 JWT 中自报的 `research:read`、`research:write` 或 `research:execute`。权限由服务端对签名、issuer、audience、用户 subject、OAuth client ID 和独立开关进行验证后授予。

## 4. Render 服务端配置

以下均为 Render 环境变量，不是写入 GitHub 的文件。示例中的 UUID/client ID 必须替换为实际值。

### 基础身份与读取

```text
BUSINESS_MCP_ENABLED=false
BUSINESS_AGENT_SHARING_APPROVED=false
BUSINESS_MCP_RESOURCE_URL=https://research-atlas-api-test.onrender.com/research-advisor/mcp
BUSINESS_MCP_ISSUER_URL=https://tfyfupxabojddixwjkat.supabase.co/auth/v1
BUSINESS_MCP_JWKS_URL=https://tfyfupxabojddixwjkat.supabase.co/auth/v1/.well-known/jwks.json
BUSINESS_MCP_ALLOWED_SUBJECTS=<approved-supabase-user-uuid>
BUSINESS_MCP_ALLOWED_CLIENT_IDS=<approved-chatgpt-oauth-client-id>
BUSINESS_MCP_DCR_BOOTSTRAP_ENABLED=false
```

### 写入权限（初始关闭）

```text
BUSINESS_MCP_WRITE_ENABLED=false
BUSINESS_MCP_ALLOWED_WRITE_CLIENT_IDS=
BUSINESS_MCP_ALLOWED_WRITE_SUBJECTS=
```

### 多 Agent 任务执行权限（初始关闭）

```text
BUSINESS_MCP_EXECUTION_ENABLED=false
BUSINESS_MCP_ALLOWED_EXECUTION_CLIENT_IDS=
BUSINESS_MCP_ALLOWED_EXECUTION_SUBJECTS=
```

权限含义：

- `research:read`：读取授权团队上下文和运行结果。
- `research:execute`：启动或恢复会消耗模型和学术检索预算的选题任务。
- `research:write`：保存 Workspace Agent 直接生成、且未由选题引擎重复保存的版本化推荐。

执行和写入分别需要**用户 subject 白名单 + OAuth client ID 白名单 + 独立开关**。因此，即使所有团队成员都能读取，只有被列入 `BUSINESS_MCP_ALLOWED_EXECUTION_SUBJECTS` 的成员才能启动耗费预算的多 Agent 任务；只有被列入 `BUSINESS_MCP_ALLOWED_WRITE_SUBJECTS` 的成员才能提交直接推荐。所有执行/写入 client 和 subject 还必须分别属于已批准的 read client/subject 集合。初始两个 subject allowlist 都留空。禁止使用通配符。

### 当前数据访问边界（重要）

Render MCP 当前使用服务端 PostgreSQL 连接读取 Supabase 数据库；OAuth access token 用于验证用户身份、client ID 和授权范围，但不会作为用户 JWT 转发到 Supabase Data API。因此，**Supabase RLS 不会自动应用于这条直接 SQLAlchemy 数据访问路径**。

当前授权边界由以下机制共同实现：

- Supabase OAuth JWT 的签名、issuer、audience、subject 和 client ID 验证；
- 服务端 subject/client allowlists 和独立 read/execute/write scopes；
- `BUSINESS_AGENT_SHARING_APPROVED` 总开关；
- `team_evidence_bundle` 对受限数据、原始文件和私有资产的服务端过滤；
- 仅开放明确注册的 MCP 工具，不提供任意 SQL 或数据库管理工具。

因此，所有通过 read allowlist 的成员目前读取的是**同一份团队级安全上下文**，不是按成员隔离的数据库行。End-user account 仍然提供身份识别和运行审计；若未来需要成员级行隔离，必须增加应用层 row authorization，或改为使用带用户 JWT 的 Supabase Data API/RLS 路径，不能仅依赖 OAuth 登录模式。

`BUSINESS_AGENT_SHARING_APPROVED=true` 代表团队 Owner 已明确批准该 MCP 连接读取共享科研上下文。没有 Owner 批准时保持 false。

## 5. 首次 OAuth client 注册（仅在 DCR client ID 尚未知时）

如果 ChatGPT 通过 Supabase Dynamic Client Registration 创建 OAuth client，而 client ID 尚未进入 Render allowlist，可使用一次性 fail-closed bootstrap：

1. 先确认 Supabase consent 页面可访问，并且 Owner 已批准连接。
2. 在 Render 临时设置 `BUSINESS_MCP_DCR_BOOTSTRAP_ENABLED=true`、`BUSINESS_MCP_ENABLED=true`、`BUSINESS_AGENT_SHARING_APPROVED=true)，将 `BUSINESS_MCP_ALLOWED_SUBJECTS` 限定为首位测试用户，并暂时留空 `BUSINESS_MCP_ALLOWED_CLIENT_IDS`。
3. 此模式只允许 MCP OAuth discovery / client registration 流程启动。由于服务端的 approved client 集合为空，`OAuthJwtVerifier` 会拒绝**所有**访问令牌，任何 MCP 工具都不能执行。
4. 在 ChatGPT 发起 custom MCP 连接，让 Supabase 创建 OAuth client；在 consent 页面批准前暂停/拒绝本次授权，然后从 Supabase Dashboard → Authentication → OAuth Apps 读取准确的 client ID。
5. 将该 client ID 写入 `BUSINESS_MCP_ALLOWED_CLIENT_IDS`，立即把 `BUSINESS_MCP_DCR_BOOTSTRAP_ENABLED=false`，重新部署 Render。
6. 重新发起 ChatGPT OAuth 授权，确认只有该 client 和 allowlist 中的 user subject 能读取数据。

如果 ChatGPT 连接界面允许预先配置已注册 OAuth client，则优先使用预注册 client，不需要 bootstrap。**不得**把 bootstrap 长期打开，不得用 `*` 或其他通配符代替 allowlist。

## 6. MCP 工具与权限

| 工具 | 权限 | 作用 |
|---|---|---|
| `get_research_context` | read | 读取团队画像、成果、数据资产元信息、论文/决策记忆和 context hash |
| `get_run_history` | read | 读取 Business Agent 直接保存的历史推荐 |
| `get_research_run` | read | 读取一份已保存的推荐及 idea IDs |
| `check_topic_advisor_readiness` | read | 检查研究主线、DeepSeek Key 和预算是否允许启动 |
| `list_topic_advisor_runs` | read | 查看最近的多 Agent 选题运行 |
| `get_topic_advisor_run` | read | 读取论文筛选、候选版本、质量门槛和最终结果 |
| `start_topic_advisor` | execute | 启动一条研究主线的多 Agent 选题流程 |
| `resume_topic_advisor_run` | execute | 从最后已持久化阶段恢复失败或已停滞任务 |
| `submit_research_run` | write | 保存独立于选题引擎的直接推荐结果 |

**不提供** `save_human_feedback` MCP 工具。最终人工评价必须由已登录的团队成员通过成员 API 提交，Agent 不得代填。

当前生产引擎一次执行一条研究主线，最多分析 14 篇论文。5 个主题/80 篇论文/天是后续批量调度目标，不是当前 MCP 单次调用的能力承诺。

## 7. ChatGPT Business 接入顺序

只有 Business Workspace 的 Owner/Admin 可以创建和发布 custom MCP server connection。

1. 确认 Render consent 页面已部署且真实浏览器可访问。
2. 在 Supabase 配置 Site URL、redirect allow list 和 Authorization Path。
3. 按确认后的注册方式完成 ChatGPT OAuth client 注册。
4. 把准确 Supabase user UUID 和 ChatGPT OAuth client ID 加入 Render read allowlist。
5. 在 Owner 明确批准后，将 `BUSINESS_AGENT_SHARING_APPROVED=true` 和 `BUSINESS_MCP_ENABLED=true`。
6. 在 ChatGPT Business 网页版的 **Plugins → + → Add custom MCP server** 创建 custom MCP app，填写 MCP endpoint 并完成 OAuth；扫描工具后先私下测试，再由 Owner/Admin 发布。
7. 在 Workspace Agent builder 中添加该 app，优先选择 **End-user account**，让每个成员使用自己的 Supabase Auth 身份授权；Agent-owned account 仅适用于团队明确接受共享服务身份和共享审计归属的情况。
8. 先只测试 `get_research_context`、`get_run_history` 和 `get_research_run`。
9. 确认身份隔离和公开元数据范围正确后，再单独开放 `research:execute`。
10. 最后才考虑为特定 client 开放 `research:write`。

Workspace Agent 创建、Skill 上传、工具绑定、团队分享和 Schedule 配置在 ChatGPT Agents Builder 内完成，代码仓库不能代替这些 UI 操作。

## 8. 运行分支与部署纪律

Render 当前服务：

- 仓库：`Hu-py/research-opportunity-workbench`
- 运行分支：`feat/shared-team-workspace`
- 自动部署：关闭。

本轮开发从该运行分支建立独立 feature branch；CI 通过并审查后再合并到运行分支，然后手动部署。不要将严重分叉的 `main` 整体合并进当前服务。

## 9. 连接验收与故障排查

必须完成以下测试才可开放团队使用：

1. 未登录、错误 issuer、错误 audience、未知 subject、未知 client 均被拒绝。
2. 未批准 client 只能读取；没有 execute allowlist 时不能启动任务；没有 write allowlist 时不能提交推荐。
3. context 返回真实 Supabase 数据和 hash，不包含受限数据行或原始文件。
4. 启动任务后返回持久化 run ID；运行状态可读取；失败或停滞任务能按规则恢复。
5. 读取结果包含真实论文来源、筛选记录、候选版本和质量门槛。
6. Render 重启后运行记录仍可从 Supabase 读取。
7. 人工反馈接口仍要求团队成员身份；MCP 不具有反馈写权限。
8. 只有通过证据、可行性、可证伪性和先前研究门控的候选才能进入 review-ready 推荐包。

如果出现错误，先定位 OAuth 发现、PKCE consent、JWKS 验签、client/subject allowlist、工具 scope 或模型预算，不要通过关闭安全校验来“快速修复”。


## 10. MCP 工具版本刷新

ChatGPT Workspace 使用已审核工具定义的冻结快照。服务器部署新工具后，ChatGPT 不会自动启用它们。Owner/Admin 必须进入 Workspace Settings → Apps/Plugins，刷新现有 custom MCP app 的工具列表，审查新动作并发布更新，然后在 Workspace Agent Builder 中确认工具已可用。不要删除并重建 app，除非刷新流程无法修复连接。
