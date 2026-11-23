---
name: idea_discovery
description: Construct paper-scale research opportunities from verified research gaps, cross-paper evidence and transferable mechanisms.
version: 1.1.0
---

# Idea Discovery Skill

## Objective

Generate a small number of research opportunities that can sustain a coherent paper. Do not optimize for idea count. Start from an evidenced scientific problem, not a method name or a list of keywords.

## Five legitimate innovation routes

1. Construct or measurement: identify a missing or invalid construct, explain why existing proxies fail and propose a defensible measurement strategy.
2. Mechanism or theory: identify a relationship or process not explained by current theory; state the causal or explanatory bridge and competing mechanisms.
3. Identification or validation: expose a weak identification strategy, external-validity gap, spatial/temporal leakage risk or inadequate benchmark; propose a stronger design.
4. Method capability: show that a method solves a specific bottleneck that current methods cannot, and establish input/output compatibility and a falsifiable comparison.
5. New empirical understanding: use a defensible design to reveal a generalizable pattern, boundary condition, inequality or spatial process not explained by current evidence.

Combining methods is allowed only when the combination creates a new capability or explanatory chain. It is not a contribution by itself.

## Construction workflow

1. Extract the seed paper's core question, object, construct, method, result and limitations.
2. Build an evidence map of direct, indirect, counterexample and unlinked papers.
3. Identify the unresolved bottleneck that connects the seed paper to a broader scientific question.
4. Generate competing candidate routes before selecting one. Do not force every source group to contribute to every idea.
5. For each route, state the core research question, mechanism, hypothesis, contribution type, required data, method, baselines, validation and failure condition.
6. Compare the route with its closest prior art. Explicitly state what the nearest papers already solved and what they did not.
7. Select at most one main topic and two alternatives. If none survives the critique, return no recommendation and explain why.

## Paper-scale threshold

A candidate is not paper-scale if it is only:
- a new algorithm applied to another city without a new scientific question;
- one additional feature, proxy or data source without a construct or mechanism contribution;
- a small parameter or architecture adjustment;
- a list of loosely connected methods;
- an untested claim that a method is more accurate or generalizable;
- a broad perspective topic with no defensible nearest-neighbor distinction.

A paper-scale candidate should change what researchers can explain, measure, identify, validate or decide. It must have a coherent question and enough empirical/theoretical scope to support the intended article type.

## Output

For each candidate provide:
- title and one-sentence thesis;
- research question and testable hypothesis;
- continuity with the seed paper;
- exact gap and supporting paper IDs;
- closest prior work and the difference;
- contribution type and why it matters;
- method mechanism and data requirements;
- baseline, validation and stop condition;
- risks and unresolved evidence.

Return GO, HOLD or REJECT with reasons. Never claim novelty verified from metadata alone.