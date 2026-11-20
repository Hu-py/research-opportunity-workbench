# R7.2.4｜控制组虚构科学问题编号隔离

## 真实失败记录

在 R7.2.3 的Shen et al. 2026 TRD 同源复测中，gate-off 完成5次模型调用后，`research_redesign` 输出未经定义的 `Q###` 科学问题编号。gate-off原则上不运行 scientific_value_triage，因此不存在合法Q编号。原 `research_routes` 对所有非空Q编号进行白名单校验，抛出 `Fabricated reference: route scientific question` 导致支付过的路线结果和报告无法交付。gate-on未执行。历史检查点继续冻结。

## 修复原则

- 科学门控 OFF 时，明确强制忽略模型自报Q编号；不创建/猜测一个科学问题、不加入已验证机制、不把它写进报告。
- 审计 `ignored_ungated_frontier_refs`，质量警告明确说明已忽略虚构Q编号。
- 科学门控 ON 时，仍严格要求 Q 引用在真实 triage 科学问题中存在，否则隔离不合格研究路线。
- 同样保留此前R7.2.3的独立审稿保守HOLD，不准自动对遗漏审稿的方案推荐为独立论文。

## 验收

- 完整mock gate-off新测试证明模型虚构Q999仍能完成报告，最终报告不出现Q999，审计数为1。
- gate-on引用未知Q仍被隔离。
- CI全量通过、Render新版本live后，新建同来源冻结事实的新pipeline_SHA A/B，先完成双报告再盲评。
