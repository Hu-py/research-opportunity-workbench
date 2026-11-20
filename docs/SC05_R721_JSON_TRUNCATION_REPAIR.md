# R7.2.1｜DeepSeek结构化输出截断修复（真实运行回溯）

输入：R7.2 pair `sc05pair_32bbfa109afa426e9051e1b0e69d`（Shen et al. 2026 TRD）。

## 确认事实

- gate-off完整完成：19次模型调用，文献来源ID A2/B2/C3/D9；最终进入同领域文献16篇、摘要核验12篇，A/B规划覆盖齐全。
- gate-on前4个调用和检查点已保存，但 `evidence_questions` 的DeepSeek响应因 `finish_reason=length` 抛出“模型输出被截断”；该失败不是科研质量判定。
- 失败实验不可用更改后的pipeline SHA静默续跑；R7.2.1必须建新配对，新哈希下完整运行，保留原报告、调用和错误。

## 修复

- `evidence_questions` 将自由输出限制到最多5条、每条5–12关键词，并显式设置4800输出Token预算（原为默认3300）。
- `literature_assessment` 输出预算4100→5200，优先只关联真实机制相关的1–2个诊断。
- `research_redesign` 最多3条路线、优先形成1条综合议程，输出预算6800→7200。
- `independent_critic` 输出预算3000→4100。
- 没有新增DeepSeek阶段或额外默认调用；仅为必要JSON输出留出空间，需检查每天Token预算。
- 新增离线流水线测试，验证阶段输出上限、简洁查询提示与真实数据结构整合。

## 验收

所有CI必须通过；新版本真实配对先gate-off再gate-on完成并取得两份报告，然后才可执行盲评和与人工讨论版比较。继续要求真实近邻、独立科研贡献、可行数据、规划决策；允许全HOLD或零议程。
