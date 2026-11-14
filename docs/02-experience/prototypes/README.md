# 可交互原型与版本存档

- **历史快照**保存在 `milestones/vX.Y/index.html`，一经确认不得覆盖。
- **当前批准入口** `current/index.html` 仅作跳转，避免重复存储相同 HTML。
- 每次重要调整需要更新 `../CHANGELOG.md` 与 `../design-decisions.md`，并通过 GitHub PR 评审。
- 方案页是设计决策来源；原型是交互演示；实际 Next.js 前端以 `frontend/` 为准。
- 原型没有真实登录、科研检索、模型密钥、持久化、成员权限或数据操作；不得当作生产网站。
- 本次 V0.5 原文件 SHA-256：`6660db45ae639242233f67b954c964a198c5b4a294c0f3d5f0fdd9bce51ad320`。
