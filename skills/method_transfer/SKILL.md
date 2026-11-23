---
name: method_transfer
description: Mechanism-based transfer of computational and analytical methods into urban planning and urban-science research.
version: 1.1.0
---

# Method Transfer Skill

Do not transfer a method because its name is fashionable or its source paper is highly cited. Transfer only when the source method solves a capability gap that exists in the target research problem.

## Required mapping

1. Target bottleneck: what cannot currently be measured, explained, predicted, identified or decided?
2. Source capability: what exact technical capability does the method provide?
3. Mechanism bridge: why should that capability address the target bottleneck? State the intermediate assumptions.
4. Input contract: required features, labels, graph structure, temporal sequences, text/images, supervision and preprocessing.
5. Output contract: prediction, representation, ranking, counterfactual, generated state, uncertainty or decision; define what it means in the target study.
6. Assumption compatibility: sample size, label density, spatial/temporal dependence, distribution shift, stationarity, causal assumptions, compute and calibration.
7. Adaptation: what must change in the architecture, loss, sampling, graph, training regime or evaluation?
8. Baselines: at least one simple baseline and one strong domain-appropriate competitor.
9. Falsifiable pilot: smallest dataset and experiment that could show the method does not help.
10. Failure boundaries: when should the method not be used, and what result would stop the research route?

## Transfer decision

Classify each mapping as:
- direct_transfer: input/output and assumptions are already compatible;
- conditional_transfer: feasible after explicit adaptations;
- conceptual_transfer: useful as a design principle, not a ready-to-run model;
- non_transferable: core assumptions conflict with the target problem.

## Required output

| Item | Source method | Target problem | Evidence / assumption | Required adaptation | Baseline and validation | Failure boundary |
|---|---|---|---|---|---|---|

Explain the scientific mechanism, not only the architecture. State whether the transfer creates a theoretical, measurement, identification, validation or engineering contribution. A new model name or a combination of methods is not itself a scientific contribution.