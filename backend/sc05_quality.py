"""Deterministic provenance/coverage gates for paper-only SC05 reports.

Structural checks cannot adjudicate the scientific truth of a hypothesis.
They are meant to expose shallow or unsupported model outputs to the reviewer,
not replace the blind human scientific-quality rubric.
"""
from __future__ import annotations
from typing import Any


def inspect_report(record: dict[str, Any]) -> dict[str, Any]:
    facts=record["snapshot"]["observations"]
    diagnosis=record["diagnosis"]
    issues=diagnosis.get("diagnoses",[])
    routes=record.get("routes",[])
    reviews=record.get("reviews",[])
    papers={p["id"]:p for p in record.get("external_papers",[])}
    checked={x["paper_id"] for x in record.get("literature_assessments",[])}
    kinds={x["fact_type"] for x in facts}
    source_validated=all(
        f["fact_id"].startswith("F") and f["section"].startswith("page_")
        and len(f["verbatim_excerpt"])>=12 for f in facts
    )
    grounded_issues=sum(bool(x.get("fact_ids")) for x in issues)
    falsifiable=sum(
        bool(x.get("verification_tests")) and bool(x.get("rival_explanations"))
        for x in issues)
    routes_with_nearest=sum(bool(x.get("closest_paper_ids")) for x in routes)
    routes_with_checked_nearest=sum(any(
        pid in checked for pid in route.get("closest_paper_ids",[])
    ) for route in routes)
    method_links=record.get("method_lineage",{}).get("links",[])
    measured_types={x.get("measurement_status") for x in method_links}
    flags=[]
    if "other" in kinds:
        flags.append("部分原文事实的模型分类未识别；引文已经核验但其研究语义类别仍需人工复核")
    for needed in ("objective","method","data","result"):
        if needed not in kinds:
            flags.append("论文未恢复足够的 "+needed+" 原始事实；需回看来源页")
    if not source_validated:flags.append("来源字段不完整")
    if len(method_links)<2:flags.append("计算与测量依赖链较短，可能漏掉关键公式或评估环节")
    if issues and grounded_issues<len(issues):
        flags.append("存在没有来源事实的诊断")
    if issues and falsifiable<len(issues):
        flags.append("部分诊断缺少竞争性解释或证伪检查")
    if record.get("search_errors"):
        flags.append("外部检索失败或部分失败，不能据此认定研究空白")
    if routes and routes_with_checked_nearest<len(routes):
        flags.append("部分研究路线缺少经过摘要核验的近邻研究")
    if routes and not record.get("external_papers"):
        flags.append("候选路线尚无外部文献证据，必须保持探索性")
    if any(x.get("verdict")=="test" for x in reviews) and (
        not record.get("external_papers")
    ):
        flags.append("建议进入测试的路线尚无外部先例核验")
    return {
        "source_facts":len(facts),
        "fact_types":sorted(kinds),
        "method_links":len(method_links),
        "observed_derived_simulated_types":sorted(measured_types),
        "diagnoses":len(issues),
        "grounded_diagnoses":grounded_issues,
        "falsifiable_diagnoses":falsifiable,
        "external_papers":len(papers),
        "abstract_checked_papers":len(checked),
        "routes":len(routes),
        "routes_with_prior_papers":routes_with_nearest,
        "routes_with_assessed_prior_papers":routes_with_checked_nearest,
        "critic_coverage":len(reviews)==len(routes),
        "warnings":flags,
        "structural_status":"needs_review" if flags else "structurally_complete",
        "scientific_quality_certified":False,
        "novelty_certified":False,
    }
