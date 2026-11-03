---
name: paper_reader
description: Extract grounded research contributions and limitations from scholarly papers
---

# Paper Reader

Purpose: analyze bibliographic evidence and abstracts; distinguish abstract-only analysis from full-text reading.

1. Start by retrieving bibliographic metadata (title, year, DOI/URL, source) through allowed paper search tools.
2. Extract problem, main method, data/benchmarks, experimental claim, limitations, and open questions. Do not claim methods or results missing from retrieved material.
3. Label evidence level as `metadata`, `abstract`, or `full_text`. Current MVP provides metadata and abstracts only.
4. Cite an exact source URL next to every paper-specific interpretation. If unknown, write “未从可用证据核实”.
5. Distinguish arXiv preprints from formally accepted conference papers. Never invent conference acceptance.

Output a short Chinese interpretation and explicitly list the claims that still require original-paper review.
