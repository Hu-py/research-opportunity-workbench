# Research Atlas · 前端 UX V0.5

**状态：设计基线已确认（2026-11-14）；仅为设计与 HTML 演示原型，尚未迁移到生产 Next.js，也未上线。**

此目录是 V0.5 前端设计的 GitHub 正式归档。完整设计说明与持续讨论见 [ChatGPT Page：前端信息架构与交互规范 V0.5](https://chatgpt.com/space/page_b193e2a8b43881918524188e866cf34a)。

## 当前设计

- [交互式 HTML 原型 V0.5](prototypes/milestones/v0.5/index.html)：锁定的源文件。
- [当前批准版入口](prototypes/current/index.html)：指向 V0.5，不重复维护 HTML。
- [页面树与导航架构](information-architecture.md)。
- [页面规格与跳转](page-specifications.md)。
- [设计决策](design-decisions.md)。
- [版本更新记录](CHANGELOG.md)。
- [原型版本管理规则](prototypes/README.md)。

## 已确认的关键规则

1. 最左侧**只有「对话」和「研究台」两个固定一级图标入口**；对话为默认首页。
2. 二级侧栏按一级入口切换；研究台的研究专题、科研发现、知识资产、管理与设置是**二级模块**。
3. 顶部不重复导航；不显示 Slogan、营销横幅或架构总览首页。
4. 白底、黑灰文本、精细边线；各专业页面采用适合任务的信息布局。
5. 研究画像支持团队正式画像与个人私有画像两种作用域。
6. 原型数据为示例，无真实模型、API、数据库、身份及权限操作。

## 代码边界

仓库 `frontend/` 仍为实际 Next.js 应用；本里程碑**没有修改业务代码、认证、数据库或线上网站**。实施需独立 Issue / PR 和测试。设计基线批准不等于功能验收。

## 与其他文档的关系

- 产品目标：[Research Atlas 产品目标与范围](https://chatgpt.com/space/page_c8636ac18edc8191aeee11b38130b3ef)
- 科研三类场景：[Research Atlas 三类核心使用场景](https://chatgpt.com/space/page_57ecd890598881918c1694f4bb9cc45a)
- AI 工作流：[Research Atlas AI 工作流与能力架构](https://chatgpt.com/space/page_4f5d2daf5684819181b1756930835fde)
- 系统开发与配置治理：[Development Studio](https://chatgpt.com/space/page_79b08ee99e9081918e3363df6ee1e9a3)
