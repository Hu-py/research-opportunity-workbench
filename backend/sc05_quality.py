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
    literature=record.get("literature_assessments",[])
    checked={
        x["paper_id"] for x in literature
        if x.get("evidence_status")=="abstract_quote_verified"
    }
    unlinked=sum(1 for x in literature if x.get("diagnosis_link_status")=="unlinked")
    discarded_relations=sum(int(x.get("discarded_unexplained_relations") or 0) for x in literature)
    unverified_quotes=sum(1 for x in literature if x.get("evidence_status")=="quote_unverified")
    relevance_audit=record.get("search_relevance_audit") or {}
    prior_audit=record.get("prior_reference_audit") or {}
    eligible_prior_ids=set(prior_audit.get("minimum_evidence_eligible_paper_ids",[]))
    relation_counts={
        relation:sum(
            1 for item in literature
            for link in item.get("diagnosis_links",[])
            if link.get("relation_type")==relation
        )
        for relation in ("direct","indirect","counterexample")
    }
    kinds={x["fact_type"] for x in facts}
    source_validated=all(
        f["fact_id"].startswith("F") and f["section"].startswith("page_")
        and len(f["verbatim_excerpt"])>=12 for f in facts
    )
    grounded_issues=sum(bool(x.get("fact_ids")) for x in issues)
    unknown_model_statuses=sum(bool(x.get("epistemic_status_unrecognized")) for x in issues)
    unknown_model_classes=sum(bool(x.get("issue_class_unrecognized")) for x in issues)
    unknown_model_confidences=sum(bool(x.get("confidence_label_unrecognized")) for x in issues)
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
    if unknown_model_statuses:
        flags.append(str(unknown_model_statuses)+" 条诊断的模型认知状态标签不在允许集合；已保守降级为 unknown，不能视为观测事实或已验证机制")
    if unknown_model_classes:
        flags.append(str(unknown_model_classes)+" 条诊断的问题分类标签不可识别，已降级为 other")
    if unknown_model_confidences:
        flags.append(str(unknown_model_confidences)+" 条诊断的模型置信度标签不可识别，已降级为 not_assessed")
    if issues and grounded_issues<len(issues):
        flags.append("存在没有来源事实的诊断")
    if issues and falsifiable<len(issues):
        flags.append("部分诊断缺少竞争性解释或证伪检查")
    if record.get("search_errors"):
        flags.append("外部检索失败或部分失败，不能据此认定研究空白")
    if discarded_relations:
        flags.append(str(discarded_relations)+" 条文献—诊断关系缺少有效解释，已丢弃；不得作为直接、间接或反例证据")
    if unlinked:
        flags.append(str(unlinked)+" 篇文献暂未关联到具体诊断；不作为诊断关联证据")
    if unverified_quotes:
        flags.append(str(unverified_quotes)+" 篇文献的摘要引文未通过逐字核验；不作为已核验摘要证据")
    if relevance_audit.get("quarantined",0):
        flags.append(str(relevance_audit["quarantined"])+
                     " 篇候选文献未通过研究领域/摘要筛选，已隔离且不作为直接先例")
    if relevance_audit.get("source_domain")=="unresolved":
        flags.append("原文领域无法可靠识别；保留候选检索但不得确认最近先例")
    if prior_audit.get("removed_reference_count",0):
        flags.append(str(prior_audit["removed_reference_count"])+
                     " 条模型宣称的最近先例缺少同领域摘要与直接机制关联核验，已撤销引用")
    if routes and routes_with_checked_nearest<len(routes):
        flags.append("部分研究路线缺少经过摘要核验的近邻研究")
    if routes and not routes_with_nearest:
        flags.append("无任何可证实直接机制关联的最近候选论文；不得据此宣称研究空白")
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
        "unknown_model_epistemic_statuses":unknown_model_statuses,
        "unknown_model_issue_classes":unknown_model_classes,
        "unknown_model_confidence_labels":unknown_model_confidences,
        "falsifiable_diagnoses":falsifiable,
        "external_papers":len(papers),
        "external_candidates_before_domain_screen":relevance_audit.get("retrieved",len(papers)),
        "quarantined_out_of_domain_or_abstract_missing":relevance_audit.get("quarantined",0),
        "source_domain":relevance_audit.get("source_domain","unresolved"),
        "minimum_evidence_prior_papers":len(eligible_prior_ids),
        "revoked_nearest_prior_references":prior_audit.get("removed_reference_count",0),
        "literature_assessments":len(literature),
        "abstract_checked_papers":len(checked),
        "unlinked_literature_assessments":unlinked,
        "discarded_unexplained_literature_relations":discarded_relations,
        "unverified_literature_quotes":unverified_quotes,
        "literature_relation_counts":relation_counts,
        "routes":len(routes),
        "routes_with_prior_papers":routes_with_nearest,
        "routes_with_assessed_prior_papers":routes_with_checked_nearest,
        "critic_coverage":len(reviews)==len(routes),
        "warnings":flags,
        "structural_status":"needs_review" if flags else "structurally_complete",
        "scientific_quality_certified":False,
        "novelty_certified":False,
    }
