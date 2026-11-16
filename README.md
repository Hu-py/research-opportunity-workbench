# Research Atlas — 团队共享科研智能工作台

Research Atlas 将城市与跨学科研究问题、学术文献、计算方法、科研 Agent、实验记录和团队知识资产连接到同一个可追溯工作台。

## 当前工程目标

当前优先验收的闭环是：

**在 ChatGPT 中创建、运行、追踪和分析一整组真实 SC05 A/B 科研工作流评测。**

这不是对论文主题开展新的实证数据分析，而是评估 Research Atlas Agent 能否完整完成论文理解、证据重建、批判诊断、独立研究问题形成、方法迁移和可行性论证。

最终验收标准不是代码提交或 CI 通过，而是 ChatGPT 实际完成一组有来源哈希、版本哈希、模型调用、检查点、盲评、解盲比较和持久化轮次记录的真实 A/B 实验。

## 系统架构

| 层 | 技术 / 位置 | 职责 |
|---|---|---|
| ChatGPT 入口 | OAuth-protected MCP `/mcp` | 创建论文案例、A/B 配对、预检、启动、追踪、盲评和分析 |
| Web 前端 | `frontend/` · Vercel | Research Atlas 工作界面、Owner/Admin 管理和同源 API 代理 |
| 后端 | `backend/api.py` · Render FastAPI | 认证、科研工作流、工具接口和实验管理 |
| 持久化 | PostgreSQL | 用户、实验、检查点、预算、审计、轮次台账 |
| 云端执行 | `backend/sc05_worker.py` / Render Worker | 消费经 Owner 明确授权的实验队列 |
| 长期归档 | Cloudflare R2（可选） | 私有保存来源页面、检查点和报告；不替代 PostgreSQL |
| 版本与自动化 | GitHub / Actions | 代码、PR、CI、定时数据采集和部署记录 |
| 开发追踪 | `dev-tracker/` · 独立 Vercel 项目 | Issue、PR、Commit 和 CI 状态 |

浏览器通过 Vercel 服务端代理访问 Render。ChatGPT 通过独立 OAuth/PKCE MCP 入口访问 Render。模型密钥、数据库凭据、R2 密钥和后端 Bearer Token 都必须保留在服务端。

## 仓库导航

| 路径 | 用途 |
|---|---|
| `frontend/` | Next.js 页面、API 路由、会话和服务端代理 |
| `backend/` | FastAPI、Agent、Radar、SC04/SC05、权限、预算和执行器 |
| `research_workbench/` | 共享数据库模型、OpenAlex 与核心科研数据逻辑 |
| `skills/` | 版本化研究方法和 Agent 行为规范 |
| `tests/` | 后端、MCP、权限、Agent、数据和前端相关测试 |
| `scripts/` | 部署、迁移、E2E 和维护脚本 |
| `data/`、`config/` | 数据快照、运行配置和目录清单 |
| `.github/workflows/` | CI、同步、Radar 和定时任务 |
| `dev-tracker/` | 独立工程进度追踪器 |
| `docs/` | 架构、实验、运维、权限和设计文档 |

关键文档：

- [仓库总览与系统边界](docs/REPOSITORY_MAP.md)
- [文件在用 / 隔离 / 兼容 / 参考状态清单](docs/REPOSITORY_FILE_INVENTORY.md)
- [Git 分支与 PR 生命周期](docs/BRANCH_LIFECYCLE.md)
- [SC05 ChatGPT 完整工作流操作指南](docs/SC05_CHATGPT_OPERATING_GUIDE.md)
- [SC05 MCP Owner 授权与安全边界](docs/SC05_CHATGPT_MCP_OWNER_BRIDGE.md)
- [部署说明](DEPLOYMENT.md)
- [用户开通与权限政策](docs/USER_ONBOARDING_AND_PERMISSIONS.md)
- [独立开发追踪器指南](dev-tracker/README.md)

## 当前界面入口

- 首页 `/` 重定向到 `/research-atlas-v0.5.html`，由 `frontend/public/research-atlas-v0.5.html` 提供批准版主工作界面。
- 开发者中心 `/devstudio` 使用经过认证的批准版 HTML 和真实后端交互桥。
- 实验管理、SC05 管理、GitHub 动态、团队和个人研究页面位于各自的 Next.js 路由。
- `dev-tracker/` 是独立 Vercel 项目，不是嵌入在 Research Atlas 主页面里的模块。

## SC05 ChatGPT 工作流

当前 MCP 设计提供：

1. 读取 Owner 论文、实验、预算和执行器状态。
2. 从 ChatGPT 提供的提取文本创建私人论文案例，或使用已认证网页上传较大的 PDF。
3. 创建 `science_gate_off` / `science_gate_on` A/B 配对。
4. 成对预检，验证来源、pipeline、冻结证据、检查点、并发任务和预算。
5. 顺序启动：先 baseline，后 treatment。
6. 读取匿名报告、分别盲评，再解盲比较。
7. 把问题、方法、实验内容、状态、简要结果、后续和详细记录写入 PostgreSQL 轮次台账。

查看 [SC05 ChatGPT 操作指南](docs/SC05_CHATGPT_OPERATING_GUIDE.md)。真实模型启动必须有明确用户授权，并且云端执行器已通过检查。Mock 测试、部署成功和真实科研质量是不同的验收层。

## 代码状态与部署规则

- `main` 是默认主线。
- `experiment/devstudio-postgres-e2e-20261114` 是当前隔离 Render E2E / SC05 staging 分支。
- Render 隔离服务配置为手动部署，GitHub push 不代表 Render 已部署。
- 当前开发分支或 PR 的代码，不能直接视为线上服务已运行。
- 生产服务、隔离测试服务和研究实验数据必须严格分开。

分支与 PR 规则见 [BRANCH_LIFECYCLE.md](docs/BRANCH_LIFECYCLE.md)。

## 本地开发

要求 Python 3.10+、Node.js 22+。

```bash
git clone https://github.com/Hu-py/research-opportunity-workbench.git
cd research-opportunity-workbench
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test,ai]'
uvicorn backend.api:app --reload --port 8000
```

另开终端：

```bash
cd frontend
npm install
npm run dev
```

本地 API 默认地址为 `http://127.0.0.1:8000`。公开网络部署不得使用无认证开发配置。

## CI 与验收

当前 CI 覆盖：

- Python 源码编译、后端集成测试和 Agent / API 测试；
- Streamlit legacy UI 兼容烟测；
- Next.js TypeScript 检查与生产构建；
- 独立开发追踪器静态检查。

建议执行：

```bash
python -m pytest -q
cd frontend && npm run typecheck && npm run build
```

CI 通过不代表 ChatGPT MCP 已连接，不代表 Render 已部署，也不代表真实 DeepSeek 实验已经完成。

## 兼容与历史文件

`app.py` 是旧 Streamlit 原型，目前不是主 Web 首页，但仍被 CI 兼容烟测使用。`requirements.txt` 是旧环境依赖清单，主 Python 项目依赖以 `pyproject.toml` 为准。隔离测试脚本、历史快照和设计原型不应被误删。

完整状态见 [文件使用清单](docs/REPOSITORY_FILE_INVENTORY.md)。

## 安全规则

不得将以下内容提交到 GitHub 或粘贴到 ChatGPT：

- API Key、DeepSeek Key、OAuth Token、Owner 密码；
- PostgreSQL URL、R2 Secret、Vercel / Render 服务凭据；
- 未发表论文、原始研究数据、参与者数据和私人 PDF。

真实运行、数据访问、模型调用和部署变更必须遵守对应的 Owner 授权、预算、隔离和审计规则。
