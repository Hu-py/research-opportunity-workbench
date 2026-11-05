import backend.llm_discovery as discovery

def test_llm_plans_distinct_search_angles(monkeypatch):
    calls={}
    def fake(key,model,system,payload,client=None,max_tokens=2000):
        calls["payload"]=payload
        return ({"concept_map":["urban systems","graph learning"],
          "queries":[
            {"query":"urban vertical functional transformation","mode":"direct","intent":"core question"},
            {"query":"graph transfer learning for spatial systems","mode":"method","intent":"method transfer"}],
          "blind_spots":["cross-city validation"]},{"input_tokens":10,"output_tokens":20})
    monkeypatch.setattr(discovery,"request_json",fake)
    plan,usage=discovery.plan_queries("key","deepseek-v4-pro",
      {"name":"urban vertical functions","problem":"how building functions change vertically"},
      [{"name":"building floor POI","coverage":"Shanghai","period":"2022"}])
    assert len(plan["queries"])==2
    assert plan["queries"][1]["mode"]=="method"
    assert "registered_data_assets" in calls["payload"]

def test_llm_semantic_assessment_uses_problem_fit_not_keyword_count(monkeypatch):
    def fake(key,model,system,payload,client=None,max_tokens=2000):
        assert "不得使用关键词命中数量" in payload["task"]
        paper=payload["retrieved_papers"][0]
        return ({"assessments":[{
          "paper_id":paper["paper_id"],"relevance_type":"method_transfer",
          "relevance_score":91,"method_transfer_score":96,"evidence_confidence":"medium",
          "priority":"high_priority","research_problem":"transfer across cities",
          "method":"graph representation learning","contribution_claim":"new transfer strategy",
          "limitation_or_unknown":"limited external validation","why_relevant":"method transfers",
          "data_fit":"building and POI data can support tests","follow_up_query":"cross-city graph transfer"}]},
          {"input_tokens":30,"output_tokens":40})
    monkeypatch.setattr(discovery,"request_json",fake)
    rows,usage=discovery.assess_papers("key","deepseek-flash",
      {"name":"vertical urban functions","problem":"building floor function prediction"},
      [{"name":"building floor POI","coverage":"Shanghai"}],
      [{"paper_id":"W123","title":"Graph transfer for ecological networks","abstract":"We propose graph domain transfer."}])
    assert rows[0]["relevance_type"]=="method_transfer"
    assert rows[0]["relevance_score"]==91
    assert rows[0]["human_review_required"] is True
    assert rows[0]["novelty_verified"] is False
