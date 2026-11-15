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
from backend.sc05_research_diagnosis import (
    EvidenceError, SYSTEM_PROMPT, freeze_blind_input, model_payload,
    required, text_items, validate_diagnosis,
)

VERSION = "sc05-paper-only-v0.2.0"
MODEL = "deepseek-flash"
FACT_KINDS = {"objective", "data", "method", "evaluation", "result", "limitation"}
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
LITERATURE_SCHEMA = {"assessments": [{
    "paper_id": "doi:10.xxxx/yyyy",
    "diagnosis_ids": ["D01"],
    "tested_problem": "What this actual abstract says was investigated",
    "method": "Reported methods only, otherwise not reported",
    "relevance": "close|partial|counterexample|low",
    "conditional_transfer": "Which evidence assumptions need to hold",
    "unresolved": "What the abstract does not establish",
    "abstract_excerpt": "An exact contiguous 12-150 character excerpt if abstract exists",
}]}
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
    if len(batches) > max_calls - 6:
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
            kind = item.get("fact_type")
            quote = item.get("verbatim_excerpt")
            if page not in pages or page not in [x["page"] for x in chunk]:
                raise EvidenceError("Fact cites a page outside its source batch")
            if kind not in FACT_KINDS:
                raise EvidenceError("Unsupported fact type")
            if not isinstance(quote, str) or not 12 <= len(quote) <= 400 or quote not in pages[page]:
                raise EvidenceError("Model supplied an unverified PDF quote")
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
                "search diagnosis", allow_empty=not ids),
            "query": _limited(item.get("query"), "search query", 190),
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
    """Do not allow fabricated nearest-paper details or invented abstracts."""
    rows=raw.get("assessments")
    if not isinstance(rows,list) or len(rows)>25:
        raise EvidenceError("Invalid literature assessment batch")
    allowed={p["id"]:p for p in external_papers}
    diag_ids={d["id"] for d in diagnosis["diagnoses"]}
    result=[];seen=set()
    for item in rows:
        if not isinstance(item,dict):raise EvidenceError("Invalid literature assessment")
        pid=item.get("paper_id")
        if pid not in allowed or pid in seen:
            raise EvidenceError("Literature assessment cites unknown/duplicate paper")
        seen.add(pid)
        if item.get("relevance") not in ("close","partial","counterexample","low"):
            raise EvidenceError("Invalid paper relevance")
        excerpt=item.get("abstract_excerpt")
        abstract=allowed[pid]["abstract"]
        if abstract:
            if not isinstance(excerpt,str) or not 12<=len(excerpt)<=150 or excerpt not in abstract:
                raise EvidenceError("Literature evidence quote does not match OpenAlex abstract")
        elif excerpt not in ("",None):
            raise EvidenceError("No abstract available for claimed evidence quote")
        result.append({
            "paper_id":pid,
            "diagnosis_ids":_references(item.get("diagnosis_ids"),diag_ids,
                "literature diagnosis",allow_empty=not diag_ids),
            "tested_problem":_limited(item.get("tested_problem"),"tested_problem"),
            "method":_limited(item.get("method"),"paper method"),
            "relevance":item["relevance"],
            "conditional_transfer":_limited(item.get("conditional_transfer"),"transfer"),
            "unresolved":_limited(item.get("unresolved"),"literature scope"),
            "abstract_excerpt":excerpt or "",
            "level":"OpenAlex abstract only" if abstract else "metadata only",
        })
    return result


def research_routes(raw: dict, diagnosis: dict, external_papers: list[dict]) -> list[dict]:
    rows = raw.get("routes")
    if not isinstance(rows, list) or len(rows) > 5:
        raise EvidenceError("Expected 0-5 possible research routes")
    ids = {x["id"] for x in diagnosis["diagnoses"]}
    paper_ids = {p["id"] for p in external_papers}
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
                "route diagnosis", allow_empty=not ids),
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
    if not papers:
        buf+=["", "未检索到可核验的外部文献；不能据此判断创新性。", ""]
    else:
        checked={x["paper_id"]:x for x in result["literature_assessments"]}
        buf+=["", "| 文献 | 年份/判断 | 相近机制与适用边界 |",
              "|---|---|---|"]
        for paper in papers.values():
            assessment=checked.get(paper["id"])
            status=assessment["relevance"] if assessment else "未详审"
            assessment_summary=(assessment["tested_problem"]+"；"+
                assessment["conditional_transfer"]+"；未确定："+assessment["unresolved"]
                if assessment else "仅定位到摘要或元数据，未作机制比较")
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
            "**相关诊断**："+", ".join(route["diagnosis_ids"]), "",
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
    test=[r["id"] for r in result["reviews"] if r["verdict"]=="test"]
    hold=[r["id"] for r in result["reviews"] if r["verdict"]=="hold"]
    reject=[r["id"] for r in result["reviews"] if r["verdict"]=="reject"]
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
    ]
    return "\n".join(buf)+"\n"


def run_paper(
    pdf: str | Path, api_key: str, *, model_call: Callable = request_json,
    search_provider: Callable | None = None, max_calls: int = 18,
    source_title: str | None = None,
) -> tuple[str, dict]:
    """Run a fully paper-only report. Caller must authorize provider spend."""
    if not api_key or not api_key.strip():
        raise EvidenceError("DeepSeek key unavailable; no model call initiated")
    pages,pdf_hash = page_texts_from_pdf(pdf)
    if len(_chunks(pages)) + 6 > max_calls:
        raise EvidenceError("PDF exceeds maximum authorized model call budget")
    log: list[dict] = []
    ledger = extract_ledger(pages, api_key, model_call, log, max_calls=max_calls)
    snapshot = ledger["snapshot"]
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
    question_raw=_run(model_call,api_key,"evidence_questions",
        "根据已有诊断及其竞争性解释提出最多7条科学检索查询，"
        "优先为可迁移理论、失败条件、已有实现和反例。"
        "不得提前宣布这些选题是创新。",
        {"diagnoses":diagnosis["diagnoses"],
         "open_questions":diagnosis["open_questions"],
         "required_json_shape":SEARCH_SCHEMA},log,max_calls=max_calls)
    questions=search_plan(question_raw,diagnosis["diagnoses"])
    papers,search_errors=openalex_search(questions,provider=search_provider)
    literature=[]
    if papers:
        assessed_raw=_run(model_call,api_key,"literature_assessment",
            "你是独立文献查新辅助员。仅凭以下真实OpenAlex摘要，逐篇核查"
            "其研究对象、实际方法、与诊断的关系、可转移的前提及未解问题。"
            "严格引用paper_id，且必须逐字摘录12-150字符原始摘要。"
            "本批最多评估20篇。不得假称阅读全文，不得宣布创新性已证实。",
            {"diagnosis":diagnosis["diagnoses"],
             "papers":[{k:p[k] for k in (
                "id","title","doi","url","year","venue","abstract")}
                for p in papers[:20]],
             "required_json_shape":LITERATURE_SCHEMA},log,max_calls=max_calls,
            max_tokens=4100)
        literature=literature_assessments(assessed_raw,papers,diagnosis)
    routes_raw=_run(model_call,api_key,"research_redesign",
        "现在才允许提出研究路线。至少比较算法、数据、评价体系、"
        "研究问题重构的适用性，但无需每类各出一个。"
        "不要默认模型更复杂就是创新。每条路线须指明原文证据、"
        "已有最接近研究、具体差异、最低代价的可证伪实验和终止条件。"
        "如果证据不足，允许输出空routes。不得声称系统查新已完成。",
        {"diagnosis":diagnosis,"method_lineage":lineage,
         "papers":[{k:p[k] for k in (
             "id","title","doi","url","year","venue","abstract")}
             for p in papers[:20]],
         "literature_assessments":literature,
         "required_json_shape":ROUTE_SCHEMA},log,max_calls=max_calls,max_tokens=4100)
    routes=research_routes(routes_raw,diagnosis,papers)
    critic_raw=_run(model_call,api_key,"independent_critic",
        "独立科学审稿人：不要附和上一个模型。检查近邻重合、"
        "证据不足、不可识别性、指标循环依赖与实施成本。"
        "允许全部hold或reject。必要数据未知时不得声称真实可验证。",
        {"routes":routes,"diagnoses":diagnosis["diagnoses"],
         "external_papers":[{k:p[k] for k in ("id","title","abstract")} for p in papers[:20]],
         "required_json_shape":CRITIC_SCHEMA},log,max_calls=max_calls,max_tokens=3000)
    reviews=critique(critic_raw,routes)
    output = {
        "version":VERSION, "source":{"title":source_title or Path(pdf).stem,
            "sha256":pdf_hash,"page_count":len(pages),"type":"uploaded_pdf"},
        "snapshot":snapshot,"method_lineage":lineage,
        "diagnosis":diagnosis,"search_queries":questions,
        "external_papers":papers,"search_errors":search_errors,
        "literature_assessments":literature,
        "routes":routes,"reviews":reviews,"usage":log,
        "is_paid_model_output":True,"independent_raw_data_validation":False,
        "novelty_proved":False,
    }
    return _markdown(output),output
