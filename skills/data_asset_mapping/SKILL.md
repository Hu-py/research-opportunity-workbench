---
name: data_asset_mapping
description: LLM-led mapping between research questions, team data assets and verified team achievements.
---

# Data Asset Mapping Skill

Map research lines to registered data assets and verified team achievements by understanding research constructs, observational units, spatial and temporal coverage, fields, methods and evidence gaps. Do not use keyword overlap as the decision rule.

Only inspect non-restricted dataset metadata and verified team achievement metadata. Never read raw files, private paths, personal records, restricted datasets or credentials.

For each proposed relation, explain the exact research construct it can support, the relevant fields or coverage, what is missing, and what must be checked before the data can be used. A registry record does not prove data access, quality, licensing, representativeness, or valid measurement.

Return exact reference IDs from the supplied inventory only. Classify relation strength as 0-100 triage score, but explain that this is a model judgement rather than a calibrated probability. Distinguish direct empirical support, contextual support, possible method validation, and weak association.

Do not force every asset into a research line. Return no relation when there is no defensible conceptual connection. All model-generated links remain suggested until a human reviewer confirms them.