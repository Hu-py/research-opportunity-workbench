# Decisions and audit

2026-11-07: reviewed profile_database, preanalysis, weekly_synthesis, research_evidence_export, model_gateway, research_budget, discovery, ai_lab, scientific_agent, scientific_tournament, API dependencies and Next.js integration.

Reuse existing SQLAlchemy Base, JSON DeepSeek adapter, four-stage prompts and strict citation validators. Existing daily guardrail is not a cumulative CNY limit; a task-scoped durable call ledger supplements it. Use peak cache-miss prices conservatively (Flash 2/8 CNY per million input/output tokens; Pro 9/27), verified against https://api-docs.deepseek.com/zh-cn/quick_start/pricing/ on 2026-11-07. Failures retain reservations, no automatic retry, concurrency one, output capped at 4000 tokens. This is a conservative estimate, not an invoice.

Research Agent Lab read-only review at 94845f3247a02b678e147918d2b160d8cd91c126: workflow.py uses independent lens proposals, review, critique/revision and bounded rounds. frontier/feasibility_gate.py verifies registered fields, access and executable empirical protocols. Reuse evidence/uncertainty principles, but do not import its experiment execution requirements into topic advice or mutate that repository.

Initial live failures: missing mandatory `why_now` on a second generated topic, plus truncated JSON. Improvement: common concise field constraints, one complete topic per proposal, larger bounded output ceiling. Preserve rejected raw responses in local audit storage. A/B/C share frozen evidence but differ in request counts; describe this explicitly.

Reviewer independence: Pro reviews Flash outputs in new contexts with anonymized labels; two perspectives are not two independent model families or human reviewers. Synthetic team capability statements are never facts about the real team. Public bibliography is not human-approved literature; A is a prompt-level replay on that frozen evidence, not a claim that production eligibility gates were passed.

Follow-up: cardinality is owned by each stage's validator, never a global model-transport instruction. A's original prompts must remain unchanged for faithful baseline comparison. A one-call live reader probe supports complete evidence coverage under the corrected contract; it does not establish improved topic value. No further paid experiments during branch publication/review.
