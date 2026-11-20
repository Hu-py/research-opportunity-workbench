"""Offline R7.2 source-ID and scoped recovery contracts; never hit OpenAlex."""
from backend.sc05_source_resolution import resolve_sources
from backend.sc05_paper_only import recover_coverage_papers


def test_verified_approved_venue_ids_from_exact_openalex_results_only():
    lookups=[]
    def find(name):
        lookups.append(name)
        # The first result is deliberately an irrelevant near-name match.
        return [
            {"id":"https://openalex.org/S999","display_name":name+" X"},
            {"id":"https://openalex.org/S123456","display_name":name},
        ]
    ids,audit=resolve_sources([], "urban_transport",search_sources=find)
    assert ids["A"]==["S123456"]
    assert ids["B"]==["S123456"]
    assert ids["D"]==["S123456"]
    assert len(lookups)>=14
    assert audit["openalex_exact_name_sources"]==len(lookups)
    assert audit["provider_errors"]==[]
    assert audit["strict_exact_name"] is True


def test_ambiguous_venue_id_cannot_be_guessed():
    def find(name):
        return [{"id":"https://openalex.org/S100","display_name":name},
                {"id":"https://openalex.org/S200","display_name":name}]
    ids,audit=resolve_sources([], "urban_transport",search_sources=find)
    assert ids["A"]==ids["B"]==ids["C"]==ids["D"]==[]
    assert len(audit["unresolved"])>=4
    assert audit["unresolved"][0]["reason"]=="ambiguous_exact_ids"


def test_owner_approved_source_id_frozen_without_overriding():
    owner=[{"name":"Cities","openalex_source_id":"S1001","enabled":True},
           {"name":"Transportation Research Part D",
            "openalex_source_id":"https://openalex.org/S4001","enabled":True},
           {"name":"Sustainable Cities and Society",
            "openalex_source_id":"S7777","enabled":False}]
    requested=[]
    def find(name):
        requested.append(name)
        return []
    ids,audit=resolve_sources(owner,"urban_transport",search_sources=find)
    assert "S1001" in ids["A"]
    assert "S4001" in ids["D"]
    assert "S7777" not in str(ids)
    assert "Cities" not in requested
    assert "Transportation Research Part D: Transport and Environment" not in requested
    assert audit["owner_registered_exact_sources"]==2


def test_lookup_errors_are_sanitized_and_do_not_invent_ids():
    def broken(name):
        raise ValueError("https://api.openalex.org/sources?api_key=PRIVATE")
    ids,audit=resolve_sources([], "urban_transport",search_sources=broken)
    assert not any(ids.values())
    assert audit["provider_errors"][0]["error_type"]=="ValueError"
    assert "PRIVATE" not in str(audit)


def test_bounded_recovery_fills_missing_A_B_D_without_auto_approval():
    venues={"A":"Cities","B":"Computers, Environment and Urban Systems",
            "D":"Transportation Research Part C: Emerging Technologies"}
    queries=[]
    def mock_search(specs,*,source_profile,source_ids_by_tier):
        tier=specs[0]["source_tier_intent"]
        queries.append(tier)
        assert source_ids_by_tier[tier]==["S"+{"A":"1","B":"2","D":"4"}[tier]]
        return [{
            "id":"doi:10.1000/"+tier.lower(),"doi":"10.1000/"+tier.lower(),
            "title":"Urban rail transit disruption cascading resilience "+tier,
            "url":"https://doi.org/10.1000/"+tier.lower(),
            "year":"2025-01-01",
            "venue":venues[tier],
            "abstract":"Urban rail transit disruptions shift passenger flow in metro networks with cascading effects.",
            "search_query":specs[0]["query"],
        }],[]
    rows,errors,audit=recover_coverage_papers(
        [], {"code":"urban_transport"},
        {"A":["S1"],"B":["S2"],"D":["S4"],"C":[]},
        retriever=mock_search,
    )
    assert errors==[]
    assert queries==["A","B","D"]
    assert audit["added_papers"]==3
    assert len(rows)==3
    # Later existing source+abstract checks can accept only approved actual venues.
    from backend.sc05_relevance import screen_candidate_papers
    from backend.sc05_source_policy import apply_source_governance
    screened,_=screen_candidate_papers(rows,{"code":"urban_transport"})
    direct,_,policy=apply_source_governance(rows,screened,source_domain="urban_transport")
    assert {r["source_tier"] for r in direct}=={"A","B","D"}
    assert policy["uncovered_planning_streams"]==[]


def test_recovery_does_not_call_provider_without_verified_source_id():
    def forbidden(*args,**kwargs):
        raise AssertionError("No unfiltered recovery may occur")
    rows,errors,audit=recover_coverage_papers(
        [],{"code":"urban_transport"},{"A":[],"B":[],"C":[],"D":[]},
        retriever=forbidden)
    assert rows==errors==[]
    assert audit["fallback_queries"]==[]


def test_recovery_deduplicates_existing_papers():
    prior={
        "id":"doi:10.1000/existing","doi":"10.1000/existing",
        "title":"Urban rail transit disruption resilience",
        "url":"https://doi.org/10.1000/existing",
        "year":"2025-01-01",
        "venue":"Cities",
        "abstract":"Metro transport network and passenger flow disruption impacts.",
        "search_query":"old",
    }
    def repeated(specs,*,source_profile,source_ids_by_tier):
        return [prior], []
    rows,errors,audit=recover_coverage_papers(
        [prior],{"code":"urban_transport"},
        {"A":["S1"],"B":[],"C":[],"D":["S4"]},
        retriever=repeated)
    assert len(rows)==1
    assert audit["added_papers"]==0
