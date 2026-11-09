# Adaptation review — 2026-11-07

Reviewed GitHub READMEs, repository license metadata, data notices and dependency manifests. Inspected ResearchBench ranking.py and metrics.py for the chosen task. Other systems have not been reproduced or comprehensively audited; reported capabilities are their own claims.

| Project | License and dependencies observed | Protocol and decision |
|---|---|---|
| [ResearchBench](https://github.com/ankitala/ResearchBench) | MIT code; DATA_LICENSE.md specifies CC BY-NC 4.0 data with upstream restrictions. Python >=3.10, optional OpenAI SDK; no mandatory core dependencies | Retrieval, hypothesis composition, ranking. Official ranking compares gold against negatives in both orders; its parser defaults to candidate 1 on parse failure. Adopt two local development cases, but strict JSON/coverage validation instead of default scoring. Not an official reproduction. |
| [MOOSE-Chem](https://github.com/ZonglinY/MOOSE-Chem) | MIT code; separate third-party data redistribution rights not established in this review. Requirements include torch, transformers, datasets, peft, OpenAI, pandas, pdfminer | Historical reconstruction requires question/background, inspiration corpus and a credible model knowledge cutoff. Current model contamination cannot be ruled out. No dataset import or multi-hour workflow execution. |
| [AgentIdeaBench](https://github.com/HKUST-KnowComp/AgentIdeaBench) | README MIT code; LICENSE-DATA grants CC BY 4.0 for covered generated/derived records, explicitly excludes third-party abstracts/full text and some model-generated text. Python >=3.9, OpenAI 1.82.0, requests, dotenv | Matched static vs active literature access; useful future B0/B1 design. Do not import excluded text or use automated critic scores as truth. Deferred to avoid a search-stack confound in the first baseline. |
| [PaperQA2](https://github.com/Future-House/paper-qa) | Apache-2.0 code; PDF content requires separate rights. Modern Python stack includes fhlmi, fhaviary, LiteLLM, parsing, embeddings/search dependencies | Traceable retrieval/question answering, not a direct topic-value benchmark. Future source-grounding design reference, no full dependency transplant. |

Existing architecture retained: SQLAlchemy artifacts, DeepSeek request_json, durable cost ledger and cache. Add only a task-level checkpoint/schema adapter. No new agents, production migration or personalization training.

ResearchBench source DOI identifiers for selected records: `10.1007/s00159-024-00151-2` and `10.1007/s10453-022-09750-x`. These are benchmark provenance, not independently verified endorsement of benchmark labels.
