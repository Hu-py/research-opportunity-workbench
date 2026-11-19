"""SC05 catalog and scientific-program governance; synthetic inputs, no API."""
from backend.sc05_source_policy import source_tier,apply_source_governance
from backend.sc05_relevance import screen_candidate_papers, infer_source_domain
from backend.sc05_method_transfer import collect_transfer_leads
from backend.sc05_research_program import audit_research_program, PROGRAM_FIELDS


def paper(pid,venue,title,abstract):
    return {"id":pid,"title":title,"venue":venue,"abstract":abstract,
            "url":"https://doi.org/10.1000/"+pid,"doi":"10.1000/"+pid,
            "year":"2025"}


def test_a_b_c_d_sources_are_exact_approved_and_non_catalog_quarantined():
    d="urban_transport"
    assert source_tier("Cities",d)["tier"]=="A"
    assert source_tier("Sustainable Cities and Society",d)["tier"]=="A"
    assert source_tier("Environment and Planning B",d)["tier"]=="B"
    assert source_tier("Computers, Environment and Urban Systems",d)["tier"]=="B"
    assert source_tier("NeurIPS",d)["tier"]=="C"
    assert source_tier("Transportation Research Part D",d)["tier"]=="D"
    assert source_tier("Journal of Hydrology","water_hydrology")["tier"]=="D"
    assert source_tier("Journal of Hydrology",d)["tier"]=="unlisted"
    assert source_tier("Smart Cities",d)["tier"]=="unlisted"
    assert source_tier("Unknown Philosophy Press",d)["tier"]=="unlisted"
    assert source_tier("",d)["tier"]=="unverified"


def test_venue_policy_never_mistakes_relevance_heuristic_for_approved_prior():
    source={
        "code":"urban_transport","confidence":"heuristic",
    }
    a=paper("a","Cities","Urban rail resilience during flooding",
            "Urban rail transit passenger flow management during disruptions.")
    b=paper("b","Computers, Environment and Urban Systems",
            "Metro service disruption propagation",
            "Network passenger flow adaptation between metro stations.")
    c=paper("c","NeurIPS","Graph neural network for city stations",
            "A graph neural network uses urban transit station features.")
    d=paper("d","Transportation Research Part D","Rail demand shock",
            "Urban rail transit passengers shift to buses during disruptions.")
    n=paper("n","Journal of Unrelated Philosophy",
            "Metro resilience and fairness in epistemology",
            "Urban rail transit passengers are mentioned only as metaphors.")
    items=[a,b,c,d,n]
    domain,audit=screen_candidate_papers(items,source)
    assert len(domain)==5  # coarse domain matching CAN wrongly admit everything.
    scoped,in_scope,policy=apply_source_governance(
        items,domain,source_domain="urban_transport")
    assert [p["id"] for p in scoped]==["a","b","d"]
    assert [p["id"] for p in in_scope]==["a","b","c","d"]
    assert policy["excluded_outside_catalog_ids"]==["n"]
    assert policy["direct_tiers_with_candidates"]==["A","B","D"]
    assert policy["uncovered_planning_streams"]==[]
    assert all(x["eligible_for_nearest_prior"] for x in scoped)
    assert all(x.get("domain_screen_status")=="domain_match" for x in scoped)
    leads,method_audit=collect_transfer_leads(
        in_scope,scoped,audit,forced_technical_ids={"c"})
    assert [p["id"] for p in leads]==["c"]
    assert leads[0]["eligible_for_nearest_prior"] is False
    assert leads[0]["original_screen_reason"]=="curated_C_technical_method_not_domain_prior"
    assert method_audit["auto_approved_transfers"]==0


def test_c_venue_source_paper_and_empty_abstract_do_not_enter_method_lane():
    p=paper("source","NeurIPS","Graph neural network urban rail transit",
            "We use graph neural network for metro passenger trajectories.")
    q=paper("missing","NeurIPS","Graph neural network in transportation","")
    screened,audit=screen_candidate_papers(
        [p,q],{"code":"urban_transport"},source_doi=p["doi"])
    direct,in_scope,source_audit=apply_source_governance(
        [p,q],screened,source_domain="urban_transport")
    assert direct==[]
    leads,lead_audit=collect_transfer_leads(
        in_scope,direct,audit,forced_technical_ids={"source","missing"})
    assert leads==[]
    assert lead_audit["auto_approved_transfers"]==0


def program(level="system_program"):
    return {"contribution_level":level,
      "planning_problem":"Urban evacuation and mobility loss distribution across dense city zones",
      "system_mechanism":"Cross-modal substitution changes effective network capacity and transfers risk",
      "planning_contribution":"Contrasting transport investment and operating interventions changes unequal loss",
      "decision_stakeholders":"Transit operators and spatial planners choose corridor upgrades and support",
      "generalization_boundary":"Compare dense and polycentric cities under different disruption intensities",
      "paper_architecture":"Study demand substitution then feedback threshold then validation and policy",
      "why_not_a_subexperiment":"It estimates feedback and policy tradeoffs absent from original index ranking"}


def test_model_prose_alone_is_not_novelty_or_paper_quality_certification():
    routes=[{"id":"R01","research_program":program(),"closest_paper_ids":["a"]},
            {"id":"R02","research_program":program("mechanism_substudy"),
             "closest_paper_ids":["a"]},
            {"id":"R03","research_program":{},"closest_paper_ids":[]}]
    reviews=[{"route_id":x["id"],"verdict":"test"} for x in routes]
    policy={"direct_tiers_with_candidates":["A","B","D"],
            "uncovered_planning_streams":[]}
    audit=audit_research_program(routes,reviews,policy)
    assert audit["recommended_for_human_independent_study_review"]==1
    assert audit["routes"][0]["editorial_status"]=="provisional_independent_study_for_human_review"
    assert audit["routes"][1]["editorial_status"]=="not_ready_to_recommend_as_independent_paper"
    assert audit["routes"][2]["missing_program_dimensions"]
    assert not audit["novelty_certified"]
    assert not audit["publisher_acceptance_certified"]
    assert not audit["review_required"] is False


def test_without_both_planning_venues_even_full_text_cannot_be_promoted():
    r={"id":"R01","research_program":program(),
       "closest_paper_ids":["d"]}
    v=[{"route_id":"R01","verdict":"test"}]
    audit=audit_research_program(
        [r],v,{"direct_tiers_with_candidates":["D"],
               "uncovered_planning_streams":["A","B"]})
    assert audit["recommended_for_human_independent_study_review"]==0
    assert "planning_A_B_evidence_coverage_incomplete" in audit["routes"][0]["cautions"]
    assert not audit["routes"][0]["planning_A_B_coverage_sufficient"]


def test_resolved_openalex_ids_are_not_invented_or_cross_domain():
    from backend.sc05_source_policy import resolved_openalex_source_ids
    rows=[
        {"name":"Cities","openalex_source_id":"S101","enabled":True},
        {"name":"Environment and Planning B","openalex_source_id":"https://openalex.org/S102"},
        {"name":"NeurIPS","openalex_source_id":"S103"},
        {"name":"Transportation Research Part D","openalex_source_id":"S104"},
        {"name":"Journal of Transport Geography","openalex_source_id":"not-resolved"},
        {"name":"Unknown Philosophy Press","openalex_source_id":"S106"},
        {"name":"Sustainable Cities and Society","openalex_source_id":"S107","enabled":False},
    ]
    ids=resolved_openalex_source_ids(rows,"urban_transport")
    assert ids=={"A":["S101"],"B":["S102"],"C":["S103"],"D":["S104"]}
    assert "S106" not in str(ids)
    assert resolved_openalex_source_ids(rows,"water_hydrology")["D"]==[]


def test_openalex_query_uses_resolved_tier_filter_without_more_api_calls(monkeypatch):
    import research_workbench.core as core
    from backend.sc05_paper_only import openalex_search
    requests=[]
    def fake_query(q,since,limit=7,**opts):
        requests.append({"query":q,"source_ids":opts.get("source_ids"),
                         "relevance":opts.get("sort_by_relevance")})
        return []
    monkeypatch.setattr(core,"query_openalex",fake_query)
    queries=[
        {"query":"urban rail flood access","need":"application","source_tier_intent":"A"},
        {"query":"city adaptation networks","need":"theory","source_tier_intent":"B"},
        {"query":"graph neural network","need":"method","source_tier_intent":"C"},
        {"query":"metro passenger reassignment","need":"validation","source_tier_intent":"D"},
    ]
    results,errors=openalex_search(queries,provider=None,
        source_profile={"code":"urban_transport"},
        source_ids_by_tier={"A":["S101"],"B":["S102"],"C":["S103"],"D":["S104"]})
    assert results==errors==[]
    assert len(requests)==4
    assert [q["source_ids"] for q in requests]==[
        ["S101"],["S102"],["S103"],["S104"]]
    assert all(q["relevance"] for q in requests)
    assert requests[2]["query"]=="graph neural network"


def test_entire_offline_paper_workflow_freezes_catalog_for_gate_on(monkeypatch,tmp_path):
    from backend.sc05_paper_only import run_paper
    from backend.sc05_research_diagnosis import model_payload
