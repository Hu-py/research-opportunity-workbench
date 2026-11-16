"""Paper-only SC05 research diagnosis -> targeted evidence -> research routes.

One PDF is the only required input. No study-specific data, code, journal
approval, or researcher-provided future plan is required for a first analysis.
Paid model calls occur ONLY when the CLI caller explicitly opts in.
Never interpret proposed hypotheses as independently validated study results.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

from backend.model_gateway import request_json
from backend.sc05_science_gate import FRONTIER_SCHEMA, validate_scientific_triage, enforce_route_frontiers
from backend.sc05_quality import inspect_report
from backend.sc05_research_diagnosis import (
    EvidenceError, SYSTEM_PROMPT, freeze_blind_input, model_payload,
    required, text_items, validate_diagnosis, verify_facts,
)

# Keep the prompt payload version stable so saved V0.2 paid checkpoints replay exactly.
VERSION = "sc05-paper-only-v0.2.0"
MODEL = "deepseek-flash"
FACT_KINDS = {"objective", "data", "method", "evaluation", "result", "limitation", "other"}
# The first real provider run showed that valid cited facts can carry
# unexpected classification labels. Do not throw away verified excerpts or
# spend another model call just to relabel them. This is a *taxonomy* repair,
# not a scientific claim; unknown labels remain explicitly "other".
FACT_KIND_ALIASES = {
    "objective": {"objective", "goal", "aim", "purpose", "research question", "research_question",
                  "background", "introduction", "motivation", "research objective", "研究目标", "研究问题", "背景"},
    "data": {"data", "dataset", "data source", "data_source", "input", "sample",
             "study area", "study_area", "dataset description", "数据", "数据来源", "研究区域", "样本"},
    "method": {"method", "methods", "methodology", "formula", "equation", "algorithm",
               "model", "index", "metric", "indicator", "calculation",
               "variable", "feature", "assumption", "approach", "方法", "公式", "模型", "指标", "计算", "假设"},
    "evaluation": {"evaluation", "validation", "experiment", "experimental design",
                   "experiment design", "comparison", "assessment", "analysis",
                   "verification", "baseline", "sensitivity", "评价", "验证", "实验", "对比", "评估"},
    "result": {"result", "results", "finding", "findings", "evidence",
               "empirical result", "empirical finding", "outcome", "conclusion",
               "observation", "effect", "discovery", "结果", "发现", "结论", "实证结果"},
    "limitation": {"limitation", "limitations", "constraint", "caveat", "scope",
                   "uncertainty", "challenge", "weakness", "boundary",
                   "限制", "局限", "不确定性", "研究边界"},
}


def normalize_fact_kind(value: object) -> tuple[str, str]:
    """Normalize a known alias; otherwise keep the cited fact unclassified.

    Returns (canonical_type, original_model_label). The exact paper quote is
    separately verified before freezing the evidence snapshot.
    """
    if isinstance(value, str):
        original=value[:150]
        label=" ".join(value.strip().casefold().replace("-", " ").replace("_", " ").split())
        for canonical, aliases in FACT_KIND_ALIASES.items():
            if label in aliases or label.replace(" ", "_") in aliases:
                return canonical,original
        return "other",original
    return "other",type(value).__name__

FUTURE_HEADING = re.compile(
    r"(?im)^\s*(?:(?:\d+(?:\.\d+)*\.)\s*)?"
    r"(?:discussion|future (?:work|research|directions)|outlook|references|bibliography)"
    r"\s*$"
)
METHOD_SCHEMA = {
    "links": [{
        "component": "Named calculation or experimental step",
        "fact_ids": ["F001"],
        "input": "Observed data or prior computed output",
        "transformation": "Formula, model, algorithm or assumption",
        "output": "Computed variable or outcome",
        "measurement_status": "observed|derived|simulated|unknown",
        "critical_assumption": "What must be true for this operation",
        "conclusion_supported": "What this step can and cannot justify",
    }],
    "claim_checks": [{
        "claim": "Strongest claim worth testing",
        "fact_ids": ["F001"],
        "unverified_link": "Why the available evidence may not fully establish it",
        "smallest_check": "Targeted falsification or sensitivity analysis",
    }],
}
SEARCH_SCHEMA = {"queries": [{
    "diagnosis_ids": ["D01"],
    "query": "Specific independently searchable research question",
    "need": "theory|method|counterexample|validation",
    "assumption_to_test": "What would change the conclusion",
}]}
ROUTE_SCHEMA = {"routes": [{
    "id": "R01",
    "title": "Distinct research question, not a renamed existing study",
    "change_kind": "model|data|evaluation|research_question",
    "diagnosis_ids": ["D01"],
    "frontier_ids": ["Q01"],
    "research_question": "Concrete new question",
    "new_mechanism": "Exactly what explanatory/technical link is being added",
    "why_previous_study_cannot_answer": "Evidence gap, not a vague novelty claim",
    "closest_paper_ids": ["doi:10.xxxx/yyyy"],
    "difference_from_prior_work": "Verifiable conditional difference",
    "feasibility": "Data or algorithm prerequisites, and fallback",
    "minimal_experiment": "Specific split, competing baselines, outcomes and checks",
    "negative_result": "A result that would reject or substantially weaken this idea",
    "unknowns": ["Missing evidence"],
}]}
# V1 is retained solely to validate/replay already-paid legacy checkpoints.
LITERATURE_SCHEMA_V1 = {"assessments": [{
    "paper_id": "doi:10.xxxx/yyyy",
    "diagnosis_ids": ["D01"],
    "tested_problem": "What this actual abstract says was investigated",
    "method": "Reported methods only, otherwise not reported",
    "relevance": "close|partial|counterexample|low",
    "conditional_transfer": "Which evidence assumptions need to hold",
    "unresolved": "What the abstract does not establish",
    "abstract_excerpt": "An exact contiguous 12-150 character excerpt if abstract exists",
}]}
LITERATURE_ASSESSMENT_SYSTEM_V1 = (
    "你是独立文献查新辅助员。仅凭以下真实OpenAlex摘要，逐篇核查"
    "其研究对象、实际方法、与诊断的关系、可转移的前提及未解问题。"
    "严格引用paper_id，且必须逐字摘录12-150字符原始摘要。"
    "本批最多评估20篇。不得假称阅读全文，不得宣布创新性已证实。"
)
LITERATURE_SCHEMA = {"assessments": [{
    "paper_id": "doi:10.xxxx/yyyy",
    "diagnosis_links": [{
        "diagnosis_id": "D01",
        "relation_type": "direct|indirect|counterexample",
        "relation_explanation": "Why this paper relates to this exact diagnosis; for indirect links explain the mechanism bridge, and for counterexamples explain the conflicting result or rival explanation",
    }],
    "unlinked_reason": "Required only when diagnosis_links is empty; explain why no diagnosis can be confidently linked",
    "tested_problem": "What this actual abstract says was investigated",
    "method": "Reported methods only, otherwise not reported",
    "relevance": "close|partial|counterexample|low",
    "conditional_transfer": "Which evidence assumptions need to hold",
    "unresolved": "What the abstract does not establish",
    "abstract_excerpt": "An exact contiguous 12-150 character excerpt if abstract exists",
}]}
LITERATURE_ASSESSMENT_SYSTEM = (
    "你是独立文献查新辅助员。仅凭以下真实OpenAlex摘要，逐篇核查"
    "其研究对象、实际方法、与诊断的关系、可转移的前提及未解问题。"
    "必须逐篇、逐个诊断建立 diagnosis_links。relation_type 只能是 direct、indirect、counterexample。"
    "direct 表示论文直接研究该诊断所指向的问题或机制；indirect 表示存在明确的中间机制桥梁，"
    "必须在 relation_explanation 中写清桥梁，不能只说主题相似；counterexample 表示论文结果、"
    "边界条件或竞争机制对该诊断构成反例或实质性限定，必须说明冲突点。"
    "一篇论文可以关联多个诊断，也可以对不同诊断使用不同关系类型。"
    "只有无法可靠对应任何诊断时才令 diagnosis_links 为空，并填写 unlinked_reason；"
    "不得为了填字段而强行关联。"
    "relevance 是文献与主题的接近程度，与 relation_type 是不同维度。"
    "严格引用 paper_id；若摘要存在，abstract_excerpt 必须是摘要中连续12-150字符原文。"
    "本批最多评估20篇。不得假称阅读全文，不得宣布创新性已证实。"
)
CRITIC_SCHEMA = {"reviews": [{
    "route_id": "R01",
    "verdict": "test|hold|reject",
    "reason": "Strongest independent critique",
    "existing_work_risk": "Nearest prior work and its overlap",
    "data_blocker": "What the paper alone cannot establish",
    "minimum_test_revision": "Smallest credible improvement",
}]}


def _limited(value: Any, field: str, n: int = 1800) -> str:
    return required(value, field, n)


def _references(refs: Any, allowed: set[str], field: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(refs, list) or (not refs and not allow_empty):
        raise EvidenceError("Missing references: " + field)
    if not all(isinstance(x, str) for x in refs) or not set(refs) <= allowed:
        raise EvidenceError("Fabricated reference: " + field)
    return list(dict.fromkeys(refs))


def page_texts_from_pdf(pdf: str | Path) -> tuple[dict[str, str], str]:
    """Return page-indexed, diagnostic-safe text and hash from a PDF file.

    Requires optional dependency: pip install pymupdf. Never reads a network
    address or sends publisher full text to GitHub. References and the
    author's explicitly labeled future-work discussion are excluded from the
    first blind analysis, while the actual methods and empirical caveats stay.
    """
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Install PyMuPDF to read PDF sources: pip install pymupdf") from exc
    data = Path(pdf).read_bytes()
    doc = fitz.open(stream=data, filetype="pdf")
    if doc.page_count < 1 or doc.page_count > 120:
        raise EvidenceError("Unsupported PDF length")
    pages: dict[str, str] = {}
    cut = False
    for i, page in enumerate(doc):
        if cut:
            break
        txt = page.get_text(sort=True)
        if not txt or len(txt.strip()) < 60:
            continue
        # A page may have the original conclusion before Discussion;
        # retain the former, remove the latter (and subsequent references).
        m = FUTURE_HEADING.search(txt)
        if m:
            txt = txt[:m.start()]
            cut = True
        if txt.strip():
            pages["page_" + str(i + 1).zfill(2)] = txt
    if not pages:
        raise EvidenceError("No extractable PDF text; an image-only scan needs OCR")
    return pages, hashlib.sha256(data).hexdigest()


def _source_doi(pages: dict[str, str]) -> str:
    """Extract DOI only from the front matter, not the References list."""
    text="\n".join(list(pages.values())[:2])
    match=re.search(r"(?:https?://doi.org/)?(10\.\d{4,9}/[^\s<>]+)",text,re.I)
    return match.group(1).rstrip(".,;)]") if match else ""


def _chunks(pages: dict[str, str], limit: int = 9400) -> list[list[dict[str, str]]]:
    """Never cut an individual page quote; distribute pages in bounded batches."""
    out: list[list[dict[str, str]]] = []
    group: list[dict[str, str]] = []
    size = 0
    for page, text in pages.items():
        # Truncation only affects what the extractor sees; record this later.
        row = {"page": page, "text": text[:limit]}
        if group and size + len(row["text"]) > limit:
            out.append(group);group=[];size=0
        group.append(row);size += len(row["text"])
    if group:out.append(group)
    return out


def _verified_excerpt(original: str, proposed: str) -> str:
    """Recover the *literal source span* when PDF line-wraps differ.

    Accept only uniquely matching whitespace normalization; never permit
    fuzzy semantics, character substitution or hallucinated references.
    Store the exact original span in the frozen evidence snapshot.
    """
    if not isinstance(proposed, str) or not 12 <= len(proposed) <= 400:
        raise EvidenceError("Invalid source excerpt")
    if proposed in original:
        return proposed
    tokens=proposed.split()
    if len(tokens) < 2:
        raise EvidenceError("PDF evidence quote is not an exact source fragment")
    pattern=r"\s+".join(re.escape(t) for t in tokens)
    matches=list(re.finditer(pattern,original))
    if len(matches)!=1 or len(matches[0].group())>600:
        raise EvidenceError("PDF evidence quote is not an exact source fragment")
    return matches[0].group()


def _source_index(pages: dict[str, str]) -> dict[str, dict[str, str]]:
    return {"uploaded_paper": dict(pages)}


def _summarise_data(facts: list[dict[str, str]]) -> tuple[str, str]:
    questions = [f["statement"] for f in facts if f["fact_type"] == "objective"]
    data = [f["statement"] for f in facts if f["fact_type"] == "data"]
    return (
        questions[0][:1300] if questions else "What does the source paper actually test?",
        data[0][:180] if data else "Units as reported in the uploaded paper",
    )


def _run(
    model_call: Callable, api_key: str, stage: str, system: str,
    payload: dict, call_log: list[dict], *, max_calls: int, max_tokens: int = 3300,
) -> dict:
    if len(call_log) >= max_calls:
        raise EvidenceError("SC05 model-call budget exhausted")
    result, usage = model_call(api_key, MODEL, system + "\n输出一个 JSON 对象。", {
        "sc05_stage": stage, "version": VERSION, **payload,
    }, max_tokens=max_tokens)
    if not isinstance(result, dict):
        raise EvidenceError("Non-JSON model result")
    # Never put API keys, source full text or raw prompts in audit logs.
    call_log.append({
        "stage": stage, "input_tokens": max(0, int(usage.get("input_tokens", 0))),
        "output_tokens": max(0, int(usage.get("output_tokens", 0))),
        "model": MODEL,
    })
    return result


def extract_ledger(
    pages: dict[str, str], api_key: str, call: Callable,
    log: list[dict], *, max_calls: int = 18,
) -> dict:
    """Extract source-backed factual observations from one paper, page by page."""
    if not pages:
        raise EvidenceError("No source pages")
    all_facts: list[dict] = []
    used: set[tuple[str, str]] = set()
    notes: list[str] = []
    batches = _chunks(pages)
    if len(batches) > max_calls - 7:
        raise EvidenceError("Paper exceeds safe analysis budget; split input or raise the opted-in max-calls")
    for chunk in batches:
        response = _run(call, api_key, "evidence_extraction",
            "作为事实抽取员，只提取作者实际报告的研究目标、数据、公式计算步骤、"
            "实证结果、验证设计和明确限制。每项引用必须从对应页逐字复制连续12-400字。"
            "不能根据讨论建议生成下一篇题目。允许本组零个事实。"
            "输出结构 {\"facts\":[{\"page\":\"page_01\",\"fact_type\":\"data\","
            "\"statement\":\"...\",\"verbatim_excerpt\":\"...\"}]}，"
            "每组最多6条，尽量覆盖公式、数据来源、验证、负面结果和情景假设。",
            {"pages": chunk}, log, max_calls=max_calls, max_tokens=2700)
        got = response.get("facts")
        if not isinstance(got, list) or len(got) > 6:
            raise EvidenceError("Invalid factual extraction count")
        for item in got:
            if not isinstance(item, dict):
                raise EvidenceError("Invalid extracted fact")
            page = item.get("page")
            raw_kind = item.get("fact_type")
            kind, kind_label = normalize_fact_kind(raw_kind)
            quote = item.get("verbatim_excerpt")
            if page not in pages or page not in [x["page"] for x in chunk]:
                raise EvidenceError("Fact cites a page outside its source batch")
            if kind not in FACT_KINDS:
                raise EvidenceError("Unsupported normalized fact type")
            # An LLM-generated quote is not evidence until it is recovered as
            # a literal span of the cited PDF page. Exclude unverifiable facts,
            # never replace the quote with a guessed or semantically similar one.
            # A cached paid response may still contain other verified facts.
            try:
                quote=_verified_excerpt(pages[page],quote)
            except EvidenceError as exc:
                if str(exc) not in (
                    "PDF evidence quote is not an exact source fragment",
                    "Invalid source excerpt",
                ):
                    raise
                notes.append({
                    "page": page, "fact_index": len(used),
                    "rule": "unverified_source_quote_rejected",
                    "action": "excluded_from_evidence",
                })
                continue
            if kind_label != kind:
                notes.append({
                    "page":page, "raw_type":kind_label,"normalized_type":kind,
                    "rule":"known alias" if kind!="other" else "unclassified; needs reviewer",
                })
            statement = _limited(item.get("statement"), "fact statement", 1100)
            key = (page, quote)
            if key in used:continue
            used.add(key)
            all_facts.append({
                "fact_id": "F" + str(len(all_facts) + 1).zfill(3),
                "fact_type": kind, "statement": statement,
                "source_id": "uploaded_paper", "section": page,
                "verbatim_excerpt": quote,
                "evidence_origin": "author_reported",
            })
    if not all_facts:
        raise EvidenceError("No factual excerpts passed page verification")
    q,unit = _summarise_data(all_facts)
    snap = freeze_blind_input(_source_index(pages), research_question=q,
        study_unit=unit, facts=all_facts,
        unknowns=["未提供原始数据、代码和独立运行记录；不进行数值复算。"])
    return {"snapshot": snap, "source_note": notes, "pages_examined": list(pages)}


def method_lineage(raw: dict, facts: list[dict]) -> dict:
    ids = {f["fact_id"] for f in facts}
    links = raw.get("links");checks = raw.get("claim_checks")
    if not isinstance(links, list) or not 1 <= len(links) <= 20:
        raise EvidenceError("Need 1-20 method/data lineage links")
    if not isinstance(checks, list) or len(checks) > 12:
        raise EvidenceError("Invalid claims-evidence checks")
    cleaned = []
    for link in links:
        if not isinstance(link, dict) or link.get("measurement_status") not in (
            "observed", "derived", "simulated", "unknown",
        ):
            raise EvidenceError("Invalid method stage")
        cleaned.append({
            "component": _limited(link.get("component"), "component", 180),
            "fact_ids": _references(link.get("fact_ids"), ids, "method fact"),
            "input": _limited(link.get("input"), "method input"),
            "transformation": _limited(link.get("transformation"), "method transform"),
            "output": _limited(link.get("output"), "method output"),
            "measurement_status": link["measurement_status"],
            "critical_assumption": _limited(link.get("critical_assumption"), "method assumption"),
            "conclusion_supported": _limited(link.get("conclusion_supported"), "method scope"),
        })
    claim_checks = []
    for c in checks:
        claim_checks.append({
            "claim": _limited(c.get("claim"), "claim"),
            "fact_ids": _references(c.get("fact_ids"), ids, "claim fact"),
            "unverified_link": _limited(c.get("unverified_link"), "gap"),
            "smallest_check": _limited(c.get("smallest_check"), "check"),
        })
    return {"links": cleaned, "claim_checks": claim_checks}


def search_plan(raw: dict, diagnoses: list[dict]) -> list[dict]:
    items = raw.get("queries")
    if not isinstance(items, list) or len(items) > 7:
        raise EvidenceError("Expected 0-7 evidence questions")
    ids = {d["id"] for d in diagnoses}
    result = []
    for item in items:
        if not isinstance(item, dict) or item.get("need") not in (
            "theory", "method", "counterexample", "validation",
        ):
            raise EvidenceError("Invalid evidence search request")
        result.append({
            "diagnosis_ids": _references(item.get("diagnosis_ids"), ids,
                "search diagnosis", allow_empty=True),
            "query": _limited(item.get("query"), "search query", 400),
            "need": item["need"],
            "assumption_to_test": _limited(
                item.get("assumption_to_test"), "search purpose", 450),
        })
    return result


def openalex_search(queries: list[dict], *, provider: Callable | None = None) -> tuple[list[dict], list[str]]:
    """Method- and counterexample-oriented discovery; not a false novelty proof."""
    from research_workbench.core import normalize_paper, query_openalex
    fn = provider or query_openalex
    seen: set[str] = set()
    papers: list[dict] = []
    errors: list[str] = []
    for spec in queries:
        try:
            found = fn(spec["query"], "2020-01-01", limit=7)
        except Exception as exc:
            errors.append("OpenAlex search failed (" + type(exc).__name__ + ")")
            continue
        for raw in found:
            if not isinstance(raw, dict):continue
            row = normalize_paper(raw) if "abstract_inverted_index" in raw or "display_name" in raw else raw
            if not isinstance(row, dict):continue
            pid = str(row.get("id") or "")
            title = str(row.get("title") or "").strip()
            if not pid or pid in seen or not title:continue
            seen.add(pid)
            doi = str(row.get("doi") or "").strip().lower()
            url = str(row.get("url") or "")
            if doi.startswith("10.") and "/" in doi:
                url = "https://doi.org/" + doi
            if not url.startswith("https://"):continue
            papers.append({
                "id": pid, "title": title[:300],
                "doi": doi[:180], "url": url[:1000],
                "year": str(row.get("published") or "")[:10],
                "venue": str(row.get("venue") or "")[:200],
                "abstract": str(row.get("abstract") or "")[:2100],
                "evidence_level": "OpenAlex metadata and abstract only",
                "search_query": spec["query"],
            })
        if len(papers) >= 35:
            break
    return papers[:35], errors


def literature_assessments(raw: dict, external_papers: list[dict], diagnosis: dict) -> list[dict]:
    """Validate literature identity, typed diagnosis links and abstract provenance."""
    rows=raw.get("assessments")
    if not isinstance(rows,list) or len(rows)>25:
        raise EvidenceError("Invalid literature assessment batch")
    allowed={p["id"]:p for p in external_papers}
    diag_ids={d["id"] for d in diagnosis["diagnoses"]}
    result=[];seen=set()
    relation_types={"direct","indirect","counterexample"}

    for item in rows:
        if not isinstance(item,dict):
            raise EvidenceError("Invalid literature assessment")
        pid=item.get("paper_id")
        if pid not in allowed or pid in seen:
            raise EvidenceError("Literature assessment cites unknown/duplicate paper")
        seen.add(pid)
        if item.get("relevance") not in ("close","partial","counterexample","low"):
            raise EvidenceError("Invalid paper relevance")

        # V2 represents relations per diagnosis: one paper can support D01
        # directly and challenge D02 as a counterexample.
        links=[]
        if isinstance(item.get("diagnosis_links"),list):
            raw_links=item.get("diagnosis_links")
            if len(raw_links)>10:
                raise EvidenceError("Too many literature diagnosis links")
            used_diag_ids=set()
            for link in raw_links:
                if not isinstance(link,dict):
                    raise EvidenceError("Invalid literature diagnosis link")
                diagnosis_id=link.get("diagnosis_id")
                if not isinstance(diagnosis_id,str) or diagnosis_id not in diag_ids:
                    raise EvidenceError("Fabricated reference: literature diagnosis")
                if diagnosis_id in used_diag_ids:
                    raise EvidenceError("Duplicate literature diagnosis link")
                used_diag_ids.add(diagnosis_id)
                relation_type=link.get("relation_type")
                if relation_type not in relation_types:
                    raise EvidenceError("Invalid literature relation type")
                explanation=_limited(
                    link.get("relation_explanation"),
                    "literature relation explanation",700)
                links.append({
                    "diagnosis_id":diagnosis_id,
                    "relation_type":relation_type,
                    "relation_explanation":explanation,
                })
            if links:
                unlinked_reason=""
            else:
                # Missing or empty links never trigger a fabricated association.
                reason=item.get("unlinked_reason")
                unlinked_reason=(
                    _limited(reason,"unlinked literature reason",500)
                    if isinstance(reason,str) and reason.strip()
                    else "模型未提供可核验的诊断关联；暂不推断关联。"
                )
        else:
            # Backward compatibility for an already-paid V1 checkpoint.
            legacy_ids=item.get("diagnosis_ids")
            legacy_ids=[] if legacy_ids is None else _references(
                legacy_ids,diag_ids,"literature diagnosis",allow_empty=True)
            links=[{
                "diagnosis_id":diagnosis_id,
                "relation_type":"direct",
                "relation_explanation":(
                    "旧版输出明确列出了该诊断编号；旧版未区分直接、间接或反例关系，"
                    "因此仅保留其显式关联，不进一步推断关系机制。"
                ),
            } for diagnosis_id in legacy_ids]
            unlinked_reason=(
                "" if links else
                "旧版输出未提供诊断编号；未推断其与任何诊断的关系。"
            )

        diagnosis_refs=[link["diagnosis_id"] for link in links]
        excerpt=item.get("abstract_excerpt")
        abstract=allowed[pid].get("abstract") or ""
        excerpt_status="metadata_only"
        verified_excerpt=""
        if abstract and isinstance(excerpt,str) and 12<=len(excerpt)<=150:
            if excerpt in abstract:
                verified_excerpt=excerpt
                excerpt_status="verified"
            else:
                # Allow PDF/API whitespace normalization, but never fuzzy text matching.
                norm=lambda value:" ".join(value.split())
                if norm(excerpt) in norm(abstract):
                    verified_excerpt=excerpt
                    excerpt_status="verified_whitespace_normalized"
                else:
                    excerpt_status="rejected"
        elif abstract and excerpt not in ("",None):
            excerpt_status="rejected"
        elif not abstract and excerpt not in ("",None):
            excerpt_status="rejected"

        evidence_status=(
            "abstract_quote_verified"
            if excerpt_status in ("verified","verified_whitespace_normalized")
            else "quote_unverified" if excerpt_status=="rejected"
            else "metadata_only"
        )
        result.append({
            "paper_id":pid,
            "diagnosis_ids":diagnosis_refs,
            "diagnosis_links":links,
            "relation_types":list(dict.fromkeys(
                link["relation_type"] for link in links)),
            "diagnosis_link_status":"linked" if links else "unlinked",
            "unlinked_reason":unlinked_reason,
            "tested_problem":_limited(item.get("tested_problem"),"tested_problem"),
            "method":_limited(item.get("method"),"paper method"),
            "relevance":item["relevance"],
            "conditional_transfer":_limited(item.get("conditional_transfer"),"transfer"),
            "unresolved":_limited(item.get("unresolved"),"literature scope"),
            # Never expose a model-provided excerpt that failed exact source checking.
            "abstract_excerpt":verified_excerpt,
            "abstract_quote_status":excerpt_status,
            "evidence_status":evidence_status,
            "level":(
                "OpenAlex abstract only" if evidence_status=="abstract_quote_verified"
                else "OpenAlex metadata; abstract quote unverified"
                if evidence_status=="quote_unverified" else "metadata only"
            ),
        })
    return result


def research_routes(raw: dict, diagnosis: dict, external_papers: list[dict], triage: dict | None = None) -> list[dict]:
    rows = raw.get("routes")
    if not isinstance(rows, list) or len(rows) > 5:
        raise EvidenceError("Expected 0-5 possible research routes")
    ids = {x["id"] for x in diagnosis["diagnoses"]}
    paper_ids = {p["id"] for p in external_papers}
    frontier_ids = {q["id"] for q in (triage or {}).get("scientific_questions", [])}
    if triage is not None:
        enforce_route_frontiers(raw,triage)
    result = [];seen = set()
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict) or row.get("change_kind") not in (
            "model", "data", "evaluation", "research_question",
        ):
            raise EvidenceError("Unsupported research route")
        rid = "R" + str(i).zfill(2)
        if rid in seen:raise EvidenceError("Duplicate route")
        seen.add(rid)
        result.append({
            "id": rid, "title": _limited(row.get("title"), "title", 190),
            "change_kind": row["change_kind"],
            "diagnosis_ids": _references(row.get("diagnosis_ids"), ids,
                "route diagnosis", allow_empty=True),
            "frontier_ids": _references(row.get("frontier_ids", []), frontier_ids,
                "route scientific question",allow_empty=triage is None),
            "research_question": _limited(row.get("research_question"), "research question"),
            "new_mechanism": _limited(row.get("new_mechanism"), "new mechanism"),
            "why_previous_study_cannot_answer": _limited(
                row.get("why_previous_study_cannot_answer"), "prior limitation"),
            "closest_paper_ids": _references(row.get("closest_paper_ids"), paper_ids,
                "prior literature", allow_empty=True),
            "difference_from_prior_work": _limited(
                row.get("difference_from_prior_work"), "prior work"),
            "feasibility": _limited(row.get("feasibility"), "feasibility"),
            "minimal_experiment": _limited(row.get("minimal_experiment"), "experiment"),
            "negative_result": _limited(row.get("negative_result"), "negative result"),
            "unknowns": text_items(row.get("unknowns"), "unknowns"),
        })
    return result


def critique(raw: dict, routes: list[dict]) -> list[dict]:
    items = raw.get("reviews")
    if not isinstance(items, list) or len(items) != len(routes):
        raise EvidenceError("Critic must cover each route")
    allowed = {r["id"] for r in routes}
    seen=set();result=[]
    for item in items:
        rid = item.get("route_id")
        if not isinstance(item, dict) or rid not in allowed or rid in seen or item.get("verdict") not in ("test", "hold", "reject"):
            raise EvidenceError("Invalid independent critique")
        seen.add(rid)
        result.append({
            "route_id": rid, "verdict": item["verdict"],
            "reason": _limited(item.get("reason"), "critic reason"),
            "existing_work_risk": _limited(item.get("existing_work_risk"), "prior work risk"),
            "data_blocker": _limited(item.get("data_blocker"), "data blocker"),
            "minimum_test_revision": _limited(
                item.get("minimum_test_revision"), "minimum test"),
        })
    return result


def _markdown(result: dict) -> str:
    """Source-linked report, grounded in actual model outputs."""
    source = result["source"]
    snap=result["snapshot"];diag=result["diagnosis"]
    method=result["method_lineage"]
    facts = {f["fact_id"]:f for f in snap["observations"]}
    papers = {p["id"]:p for p in result["external_papers"]}
    reviews = {r["route_id"]:r for r in result["reviews"]}
    def links(ids):
        return "; ".join(
            f'{x}: PDF {facts[x]["section"]}' for x in ids if x in facts
        ) or "无直接来源"
    buf = [
        "# SC05｜单篇论文自主诊断与下一篇科研机会报告",
        "", "**研究文献**：" + source["title"],
        "**原文 DOI**：" + (("https://doi.org/"+source["doi"]) if source.get("doi") else "PDF首页未识别到 DOI"),
        "**原文哈希**：" + source["sha256"],
        "**报告性质**：模型辅助研究假设；不含数据复算或实际新实验结果。",
        "**文献检索性质**：OpenAlex 元数据及摘要级近邻搜索，不是系统查新。",
        "**证据状态**：" + ("部分缺失" if result["search_errors"] else "所有记录均保留来源信息"),
        "",
        "## 1. 原研究实际完成的贡献及证据范围",
        "",
        "**研究问题**：" + diag["study_reconstruction"]["question"],
        "",
        "**贡献主张**：" + diag["study_reconstruction"]["claimed_contribution"],
        "",
        "**实际验证**：" + diag["study_reconstruction"]["what_is_actually_tested"],
        "",
        "证据：" + links(diag["study_reconstruction"]["evidence_fact_ids"]),
        "",
        "## 2. 数据—计算—评价依赖链",
        "",
        "| 环节 | 输入→计算→输出 | 属性与关键假设 | 原文证据 |",
        "|---|---|---|---|",
    ]
    for link in method["links"]:
        cells=[
            link["component"],
            link["input"]+" → "+link["transformation"]+" → "+link["output"],
            link["measurement_status"]+"；"+link["critical_assumption"],
            links(link["fact_ids"]),
        ]
        buf.append("|"+"|".join(c.replace("|","／").replace("\n"," ") for c in cells)+"|")
    buf += ["", "## 3. 研究结论与证据之间的缺口", ""]
    if not method["claim_checks"]:
        buf.append("没有足够证据提出新的主张缺口。")
    for chk in method["claim_checks"]:
        buf += [
            "### " + chk["claim"], "",
            "已知证据：" + links(chk["fact_ids"]), "",
            "尚未证实的环节：" + chk["unverified_link"], "",
            "最低成本的检查：" + chk["smallest_check"], "",
        ]
    buf += ["## 4. 自主瓶颈诊断与反向解释", ""]
    if not diag["diagnoses"]:
        buf += ["模型在当前证据下没有提出足够可证伪的瓶颈诊断。", ""]
    for issue in diag["diagnoses"]:
        buf += [
            "### "+issue["id"]+"｜"+issue["problem"], "",
            "**性质**："+issue["epistemic_status"]+"；**诊断类别**："+issue["issue_class"],
            "**原文依据**："+links(issue["fact_ids"]),
            "**竞争性解释**："+"；".join(issue["rival_explanations"]),
            "**验证与证伪**："+"；".join(issue["verification_tests"]),
            "**研究意义**："+issue["research_consequence"], "",
        ]
    buf+=["## 5. 问题驱动的外部证据与近邻工作", ""]
    if result["search_queries"]:
        for query in result["search_queries"]:
            buf += [
                "- **"+query["need"]+"**（"+",".join(query["diagnosis_ids"])+
                "）"+query["query"]+"；待检验条件："+query["assumption_to_test"],
            ]
    triage=result.get("scientific_triage",{})
    buf+=["", "## 科研严谨性审查与新科学问题分流", ""]
    for item in triage.get("issue_classifications",[]):
        buf.append("- **"+item["diagnosis_id"]+"**："+item["lane"]+
            "；原论文处理状态："+item["scope_status"]+"；"+item["reason"])
    for item in triage.get("scientific_questions",[]):
        buf+=["", "### "+item["id"]+"｜"+item["scientific_question"], "",
              "**论文已发现现象**："+item["motivating_observation"],
              "**论文证据**："+links(item["fact_ids"]),
              "**新机制假说**："+item["mechanism_hypothesis"],
              "**研究尺度/对象变化**："+item["scope_change"],
              "**为什么不是补实验**："+item["why_not_just_a_quality_fix"],
              "**区分不同机制的实验**："+item["discriminating_test"],
              "**完整科学故事**："+item["narrative_arc"],""]
    if not papers:
        buf+=["", "未检索到可核验的外部文献；不能据此判断创新性。", ""]
    else:
        checked={x["paper_id"]:x for x in result["literature_assessments"]}
        buf+=["", "| 文献 | 年份/判断 | 相近机制与适用边界 |",
              "|---|---|---|"]
        for paper in papers.values():
            assessment=checked.get(paper["id"])
            status=assessment["relevance"] if assessment else "未详审"
            if assessment:
                if assessment["diagnosis_links"]:
                    relation_text="；".join(
                        link["diagnosis_id"]+"："+link["relation_type"]+
                        "（"+link["relation_explanation"]+"）"
                        for link in assessment["diagnosis_links"])
                else:
                    relation_text="未关联："+assessment["unlinked_reason"]
                evidence_text=assessment["evidence_status"]
                assessment_summary=(relation_text+"；"+evidence_text+"；"+
                    assessment["tested_problem"]+"；"+assessment["conditional_transfer"]+
                    "；未确定："+assessment["unresolved"])
            else:
                assessment_summary="仅定位到摘要或元数据，未作机制比较"
            buf.append("| ["+paper["title"].replace("|","／")+"]("+paper["url"]+
                ") | "+paper["year"]+" / "+status+" | "+
                assessment_summary.replace("|","／").replace("\n"," ")+" |")
    if result["search_errors"]:
        buf+=["", "检索限制："+"；".join(result["search_errors"])]
    buf+=["", "## 6. 候选研究路线：增量、实验与否决", ""]
    if not result["routes"]:
        buf+=["目前证据不足以形成可靠的下一篇方案。建议先核查上面的关键缺口。", ""]
    for route in result["routes"]:
        rev=reviews[route["id"]]
        buf+= [
            "### "+route["id"]+"｜"+route["title"], "",
            "**判定**："+rev["verdict"]+"；**变化类型**："+route["change_kind"],
            "**科研问题**："+route["research_question"], "",
            "**真正增加的机制**："+route["new_mechanism"], "",
            "**原论文回答不了的原因**："+route["why_previous_study_cannot_answer"], "",
            "**相关诊断**："+", ".join(route["diagnosis_ids"])+
            "；**新科学问题**："+", ".join(route["frontier_ids"]), "",
            "**最近先例**："+("; ".join(
                "["+papers[pid]["title"]+"]("+papers[pid]["url"]+")"
                for pid in route["closest_paper_ids"] if pid in papers
            ) or "本次检索无对应先例，不能据此声称空白"), "",
            "**与已有文献的区别（待核验）**："+route["difference_from_prior_work"], "",
            "**可行性与替代方案**："+route["feasibility"], "",
            "**最小实验及评价**："+route["minimal_experiment"], "",
            "**否决条件**："+route["negative_result"], "",
            "**关键未知**："+"；".join(route["unknowns"]), "",
            "**独立反证**："+rev["reason"]+"；已有研究风险："+rev["existing_work_risk"],
            "**数据约束**："+rev["data_blocker"], "",
            "**修订后的最小实验**："+rev["minimum_test_revision"], "",
        ]
    buf+=["## 7. 决策建议与不确定性边界", ""]
    test=[r["route_id"] for r in result["reviews"] if r["verdict"]=="test"]
    hold=[r["route_id"] for r in result["reviews"] if r["verdict"]=="hold"]
    reject=[r["route_id"] for r in result["reviews"] if r["verdict"]=="reject"]
    buf+= [
        "建议优先验证："+(", ".join(test) if test else "暂无达到测试门槛的路线"),
        "暂缓："+(", ".join(hold) if hold else "无"),
        "否决："+(", ".join(reject) if reject else "无"),
        "论文无法回答的开放问题："+"；".join(diag["open_questions"]),
        "",
        "## 8. 可审计执行记录", "",
        "模型："+MODEL+"；调用次数："+str(len(result["usage"])),
        "输入 Tokens："+str(sum(x["input_tokens"] for x in result["usage"])),
        "输出 Tokens："+str(sum(x["output_tokens"] for x in result["usage"])),
        "来源事实数："+str(len(snap["observations"]))+
        "；诊断数："+str(len(diag["diagnoses"]))+
        "；外部文献数："+str(len(papers)),
        "用户未提供独立原始数据或代码，所有数量与结果均来自原文作者报告。",
        "本报告不能证明任何候选路线已经具有可发表的新颖性或真实干预效益。",
        "",
        "## 9. 报告结构质量与需要人工检查之处", "",
        "状态："+result["quality"]["structural_status"],
        "可定位事实："+str(result["quality"]["source_facts"])+
        "；公式/数据链："+str(result["quality"]["method_links"])+
        "；已核验摘要："+str(result["quality"]["abstract_checked_papers"]),
    ]
    if result["quality"]["warnings"]:
        buf += ["**需要复核**："+"；".join(result["quality"]["warnings"])]
    else:
        buf += ["结构性证据检查已通过，但尚未经过独立科学评审。"]
    return "\n".join(buf)+"\n"


def run_paper(
    pdf: str | Path | None, api_key: str, *, model_call: Callable = request_json,
    search_provider: Callable | None = None, max_calls: int = 18,
    source_title: str | None = None,
    pages_override: dict[str, str] | None = None,
    source_sha: str | None = None,
    frozen_snapshot: dict | None = None,
    scientific_value_gate: bool = True,
    legacy_literature_checkpoint: bool = False,
) -> tuple[str, dict]:
    """Run one paper with an optional shared, verified fact snapshot for A/B."""
    if not api_key or not api_key.strip():
        raise EvidenceError("DeepSeek key unavailable; no model call initiated")
    if pages_override is None:
        if pdf is None:raise EvidenceError("A PDF or extracted pages are required")
        pages,pdf_hash=page_texts_from_pdf(pdf)
        source_kind="uploaded_pdf"
    else:
        if not isinstance(pages_override,dict) or not pages_override:
            raise EvidenceError("Invalid source page set")
        if len(pages_override)>120 or sum(len(v) for v in pages_override.values())>650000:
            raise EvidenceError("Source pages exceed size limits")
        for key,txt in pages_override.items():
            if not isinstance(key,str) or not __import__("re").fullmatch(r"page_[0-9]{2,3}",key):
                raise EvidenceError("Invalid page locator")
            if not isinstance(txt,str) or len(txt)<40:raise EvidenceError("Invalid page text")
        pages=dict(pages_override)
        pdf_hash=source_sha or hashlib.sha256(
            __import__("json").dumps(pages,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        source_kind="extracted_pdf_text"
    expected_calls=(0 if frozen_snapshot else len(_chunks(pages)))+(7 if scientific_value_gate else 6)
    if expected_calls>max_calls:
        raise EvidenceError("PDF exceeds maximum authorized model call budget")
    log: list[dict] = []
    if frozen_snapshot:
        model_payload(frozen_snapshot)
        verify_facts(_source_index(pages),frozen_snapshot["observations"])
        snapshot=frozen_snapshot
    else:
        ledger=extract_ledger(pages, api_key, model_call, log, max_calls=max_calls)
        snapshot=ledger["snapshot"]
    facts = snapshot["observations"]
    lineage_raw = _run(model_call,api_key,"method_lineage",
        "独立整理数据→指标→模型/公式→验证/情景推演的完整依赖链。"
        "区分真实观测值、代数派生指标、模拟或情景结果。"
        "每个环节必须引用已核实fact_id；不要索取用户的原始数据。"
        "若某步骤的实现未在论文披露，应标为未知。",
        {"facts":facts,"required_json_shape":METHOD_SCHEMA},log,max_calls=max_calls)
    lineage = method_lineage(lineage_raw,facts)
    diagnosis_raw = _run(model_call,api_key,"diagnosis",
        SYSTEM_PROMPT + "\n必须先重建研究实际支持的结论，识别测量、"
        "验证与推断边界。不要预先猜下一篇要做什么；不强制产生诊断。",
        {**model_payload(snapshot),"method_lineage":lineage},log,max_calls=max_calls)
    diagnosis=validate_diagnosis(diagnosis_raw,snapshot)
    if scientific_value_gate:
        triage_raw=_run(model_call,api_key,"scientific_value_triage",
        "请将论文诊断划分为研究设计严谨性检查和具有独立科学价值的新问题。"
        "没有开展另一种研究不代表原论文不严谨；认可论文针对原目标的合理选择。"
        "要从真实发现的系统规律和正面结果出发，探索新的相互作用、动态反馈、"
        "跨尺度机制、边界条件和科学解释。只补验证、敏感性或替换模型不能成为下一篇的中心研究问题。"
        "每条新科学问题必须给出原文证据、竞争机制、完整研究故事及可区分机制的实验。",
        {"facts":facts,"diagnoses":diagnosis["diagnoses"],
         "study_reconstruction":diagnosis["study_reconstruction"],
         "method_lineage":lineage,"required_json_shape":FRONTIER_SCHEMA},
        log,max_calls=max_calls,max_tokens=3500)
        scientific_triage=validate_scientific_triage(triage_raw,diagnosis["diagnoses"],facts)
    else:
        scientific_triage={"issue_classifications":[],"scientific_questions":[]}
    question_raw=_run(model_call,api_key,"evidence_questions",
        "根据已有诊断及其竞争性解释提出最多7条科学检索查询，"
        "优先为可迁移理论、失败条件、已有实现和反例。"
        "不得提前宣布这些选题是创新。",
        {"diagnoses":diagnosis["diagnoses"],
         "scientific_questions":scientific_triage["scientific_questions"],
         "open_questions":diagnosis["open_questions"],
         "required_json_shape":SEARCH_SCHEMA},log,max_calls=max_calls)
    questions=search_plan(question_raw,diagnosis["diagnoses"])
    papers,search_errors=openalex_search(questions,provider=search_provider)
    literature=[]
    if papers:
        literature_system=(
            LITERATURE_ASSESSMENT_SYSTEM_V1
            if legacy_literature_checkpoint else LITERATURE_ASSESSMENT_SYSTEM
        )
        literature_schema=(
            LITERATURE_SCHEMA_V1
            if legacy_literature_checkpoint else LITERATURE_SCHEMA
        )
        assessed_raw=_run(model_call,api_key,"literature_assessment",
            literature_system,
            {"diagnosis":diagnosis["diagnoses"],
             "papers":[{k:p[k] for k in (
                "id","title","doi","url","year","venue","abstract")}
                for p in papers[:20]],
             "required_json_shape":literature_schema},log,max_calls=max_calls,
            max_tokens=4100)
        literature=literature_assessments(assessed_raw,papers,diagnosis)
    routes_raw=_run(model_call,api_key,"research_redesign",
        "现在才允许提出研究路线。至少比较算法、数据、评价体系、"
        "研究问题重构的适用性，但无需每类各出一个。"+
        ("仅能从新科学问题创建下一篇研究路线；不可将严谨性修补直接推荐为研究主题。"
          if scientific_value_gate else "基于论文证据提出新路线，但不得宣称已经证明创新性。")+
        "每条路线须指明原文证据、"
        "已有最接近研究、具体差异、最低代价的可证伪实验和终止条件。"
        "使用literature_assessments时，只能把 evidence_status=abstract_quote_verified 的条目"
        "作为摘要证据；quote_unverified 或 metadata_only 只能作为待核查线索，不能支持事实性论断。"
        "对 diagnosis_links 中的 direct、indirect、counterexample 分别解释，不得把主题相似等同于直接证据。"
        "如果证据不足，允许输出空routes。不得声称系统查新已完成。",
        {"diagnosis":diagnosis,"scientific_triage":scientific_triage,
         "method_lineage":lineage,
         "papers":[{k:p[k] for k in (
             "id","title","doi","url","year","venue","abstract")}
             for p in papers[:20]],
         "literature_assessments":literature,
         "required_json_shape":(ROUTE_SCHEMA if scientific_value_gate
              else {"routes":[{**ROUTE_SCHEMA["routes"][0],"frontier_ids":[]}]})},
         log,max_calls=max_calls,max_tokens=4100)
    routes=research_routes(routes_raw,diagnosis,papers,scientific_triage if scientific_value_gate else None)
    critic_raw=_run(model_call,api_key,"independent_critic",
        "独立科学审稿人：不要附和上一个模型。检查近邻重合、"
        "证据不足、不可识别性、指标循环依赖与实施成本。"
        "允许全部hold或reject。必要数据未知时不得声称真实可验证。",
        {"routes":routes,"diagnoses":diagnosis["diagnoses"],
         "scientific_triage":scientific_triage,
         "external_papers":[{k:p[k] for k in ("id","title","abstract")} for p in papers[:20]],
         "required_json_shape":CRITIC_SCHEMA},log,max_calls=max_calls,max_tokens=3000)
    reviews=critique(critic_raw,routes)
    output = {
        "version":VERSION, "source":{"title":source_title or (Path(pdf).stem if pdf else "uploaded-paper"),
            "doi":_source_doi(pages),
            "sha256":pdf_hash,"page_count":len(pages),"type":source_kind},
        "snapshot":snapshot,"method_lineage":lineage,
        "diagnosis":diagnosis,"scientific_triage":scientific_triage,
        "search_queries":questions,
        "external_papers":papers,"search_errors":search_errors,
        "literature_assessments":literature,
        "routes":routes,"reviews":reviews,"usage":log,
        "is_paid_model_output":model_call is request_json,
        "experiment_variant":("scientific_value_gate_on" if scientific_value_gate else "scientific_value_gate_off"),
        "shared_frozen_evidence":frozen_snapshot is not None,
        "fact_type_normalization_notes":ledger.get("source_note",[]) if not frozen_snapshot else [],
        "independent_raw_data_validation":False,
        "novelty_proved":False,
    }
    output["quality"]=inspect_report(output)
    # inspect_report owns literature-link and abstract-evidence warnings;
    # do not append duplicate warnings at the orchestration layer.
    unknown_confidence=sum(
        1 for d in diagnosis["diagnoses"]
        if d.get("confidence") == "not_assessed"
    )
    if unknown_confidence:
        output["quality"].setdefault("warnings",[]).append(
            str(unknown_confidence)+" diagnosis confidence field(s) were absent "
            "from model output and are explicitly marked not_assessed."
        )
        output["quality"]["unassessed_diagnosis_confidence_count"]=unknown_confidence
    rejected=sum(
        1 for note in output["fact_type_normalization_notes"]
        if note.get("rule")=="unverified_source_quote_rejected"
    )
    if rejected:
        output["quality"].setdefault("warnings",[]).append(
            str(rejected)+" model-extracted paper quote(s) were not verified "
            "against the cited PDF page and were excluded from evidence."
        )
        output["quality"]["unverified_quote_rejections"]=rejected
    return _markdown(output),output
