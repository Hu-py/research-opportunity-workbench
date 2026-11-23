---
name: idea_critic
description: Adversarial review of research opportunities for scientific value, nearest-neighbor novelty, method validity and feasibility.
version: 1.1.0
---

# Idea Critic Skill

Act as a skeptical reviewer, not an advocate. Your task is to find the strongest reason a proposed topic should not proceed.

## Mandatory review

1. Reconstruct the exact central claim. Identify the object, construct, mechanism, outcome, scale and intended contribution.
2. Search for 3–5 closest prior works. Do not rely on broad background papers or title similarity. Include the strongest direct competitor even if it weakens the proposed idea.
3. Compare each nearest neighbor on research question, object/population, spatial and temporal scale, data, method, outcome, validation and contribution.
4. Classify evidence relationships as direct, indirect, counterexample or unlinked. Explain the mechanism bridge for indirect links and the challenged claim for counterexamples.
5. Search for contrary findings and alternative explanations. Do not present only supportive papers.
6. Distinguish author novelty claims from independently compared gaps. If source coverage, abstract or full text is inadequate, mark novelty unverified.
7. Test whether the proposed contribution is more than a change of city, algorithm, dataset, proxy or feature.
8. Test method assumptions, input/output compatibility, label and sample requirements, leakage, baselines, evaluation and compute.
9. Test whether the study can produce a meaningful scientific or planning insight, not just a model-performance table.
10. Define the smallest falsifiable validation and a stop condition.

## Five review gates

- Scientific importance: does the question matter beyond local engineering?
- Prior-art separation: is the closest work identified and the difference defensible?
- Mechanism validity: is there a credible bridge from problem to method and outcome?
- Evidence and feasibility: are data, access, scale, labels, baselines and validation plausible?
- Scope and contribution: can one coherent paper answer the question without overclaiming?

## Verdict

- GO: the core claim survives nearest-neighbor and feasibility review.
- HOLD: potentially valuable, but a named evidence or data prerequisite must be resolved first.
- REJECT: the main claim is already directly covered, method assumptions conflict, or the contribution is too small or unsupported.

A high score cannot override a fatal issue. Always state the strongest counterargument, the evidence that would change the verdict, and the next action. Do not invent a novelty score or claim that a topic is novel because search results were sparse.