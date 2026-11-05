"""Strict scientific-output schema and evidence checks for the evolution pipeline."""
from __future__ import annotations
from backend.research_evolution import text, string_list, THRESHOLD

LENSES=("problem","method","data")
QUALITY_FLAGS=("evidence_ok","feasible","falsifiable","prior_art_checked")

def validate(stage,data,outputs,snapshot):
    if not isinstance(data,dict):
        raise ValueError("LLM必须返回JSON对象")
    papers={p["id"]:p for p in outputs.get("papers",[])}
    datasets={x["id"] for x in snapshot["datasets"]}
    if stage=="plan":
        queries=[]
        for r in data.get("queries",[])[:3]:
            if isinstance(r,dict) and isinstance(r.get("query"),str):
                q=r["query"].strip()
                if 3<=len(q)<=220 and q not in queries:queries.append(q)
        if not queries:raise ValueError("检索Agent未生成有效语义检索式")
        return {"queries":queries,"rationale":str(data.get("rationale",""))[:500]}
    if stage=="screen":
        rows={}
        for row in data.get("assessments",[]):
            if not isinstance(row,dict):continue
            pid=row.get("paper_id")
            if pid not in papers or pid in rows:continue
            if row.get("priority") not in ("keep","investigate","reject"):
                raise ValueError("论文语义审查级别无效")
            rows[pid]={"paper_id":pid,"priority":row["priority"],
                "evidence_role":text(row.get("evidence_role"),"evidence_role",420),
                "contribution":text(row.get("contribution"),"contribution",620),
                "limitations":text(row.get("limitations"),"limitations",520),
                "confidence":str(row.get("confidence","low"))[:15]}
        if not papers or set(rows)!=set(papers):
            raise ValueError("Paper Analyst必须逐篇审查所有检索论文")
        return list(rows.values())
    if stage=="paper_referee":
        selections=string_list(data.get("selected_ids"),"selected_ids",12)
        if len(selections)<2 or any(x not in papers for x in selections):
            raise ValueError("独立论文审查必须保留至少两篇真实来源")
        return {"selected_ids":selections,
                "reason":text(data.get("reason"),"reason",1000),
                "contradictions":string_list(data.get("contradictions",[]),"contradictions")}
    if stage.startswith("seed_") or stage=="revise":
        raw=data.get("candidates")
        if not isinstance(raw,list) or not 1<=len(raw)<=3:
            raise ValueError("每轮假设数量必须在1–3之间")
        valid_parents={c["id"] for lens in LENSES for c in outputs.get("seed_"+lens,[])}
        result=[]
        for i,c in enumerate(raw):
            if not isinstance(c,dict):raise ValueError("假设字段类型无效")
            paper_ids=string_list(c.get("paper_ids"),"paper_ids")
            baselines=string_list(c.get("baselines"),"baselines")
            dataset_ids=string_list(c.get("dataset_ids",[]),"dataset_ids")
            parents=string_list(c.get("parent_ids",[]),"parent_ids")
            if not paper_ids or any(x not in papers for x in paper_ids):
                raise ValueError("假设必须引用学术工具真实返回的论文")
            if not baselines:raise ValueError("假设必须提出实验基线")
            if any(x not in datasets for x in dataset_ids):
                raise ValueError("模型不能引用不存在或受限的数据资产")
            if stage=="revise" and (not parents or any(x not in valid_parents for x in parents)):
                raise ValueError("修订方案必须回溯真实初代假设")
            result.append({"id":"H_"+stage+"_"+str(i),
                "title":text(c.get("title"),"title",220),
                "question":text(c.get("question"),"question",1000),
                "method":text(c.get("method"),"method",1400),
                "prediction":text(c.get("prediction"),"prediction",800),
                "experiment":text(c.get("experiment"),"experiment",1200),
                "paper_ids":paper_ids,"dataset_ids":dataset_ids,"baselines":baselines,
                "parent_ids":parents,
                "limitations":string_list(c.get("limitations",[]),"limitations")})
        return result
    if stage in ("score_initial","score_final"):
        pool=(sum([outputs.get("seed_"+lens,[]) for lens in LENSES],[])
              if stage=="score_initial" else outputs.get("revise",[]))
        expected={c["id"] for c in pool}
        rated={}
        for x in data.get("ratings",[]):
            if not isinstance(x,dict) or x.get("id") not in expected:continue
            value=x.get("score")
            if type(value) is not int or not 0<=value<=100:
                raise ValueError("科研评分必须是0–100的整数")
            rated[x["id"]]={"id":x["id"],"score":value,
                **{k:x.get(k) is True for k in QUALITY_FLAGS},
                "reason":text(x.get("reason"),"reason",1000)}
        if not expected or set(rated)!=expected:
            raise ValueError("独立评审Agent没有对所有假设评分")
        return {"ratings":list(rated.values())}
    if stage=="challenge":
        targets={c["id"] for lens in LENSES for c in outputs.get("seed_"+lens,[])}
        queries=string_list(data.get("queries",[]),"queries",2)
        if not queries:raise ValueError("先前研究挑战Agent必须提出反证检索")
        objections=string_list(data.get("objections"),"objections")
        if not objections:raise ValueError("缺少科学反驳")
        return {"queries":[q[:220] for q in queries],"objections":objections,
                "target_ids":[x for x in string_list(data.get("target_ids",[]),"target_ids")
                              if x in targets]}
    if stage=="counter_referee":
        refs=string_list(data.get("paper_ids"),"paper_ids",7)
        if not refs or any(x not in papers for x in refs):
            raise ValueError("第二轮文献复核必须引用真实的反证检索结果")
        risk=data.get("prior_art_risk")
        if risk not in ("manageable","fatal","unknown"):
            raise ValueError("先前研究风险类别无效")
        return {"paper_ids":refs,"prior_art_risk":risk,
                "counterclaims":string_list(data.get("counterclaims",[]),"counterclaims",8),
                "reason":text(data.get("reason"),"reason",950)}
    if stage=="package":
        possible={c["id"]:c for c in outputs.get("revise",[])}
        allowed={x["id"]:x["score"] for x in outputs.get("score_final",{}).get("ratings",[])
                 if x["id"] in possible and x["score"]>=THRESHOLD
                 and all(x.get(k) is True for k in QUALITY_FLAGS)}
        picks=string_list(data.get("selected_ids",[]),"selected_ids",2)
        if not picks or any(p not in allowed for p in picks):
            raise ValueError("最终选题没有通过机器质量门控")
        path=string_list(data.get("research_path"),"research_path",7)
        if len(path)<2:raise ValueError("必须给出可执行的多步骤研究路径")
        items=[]
        for pid in picks:
            c=possible[pid]
            refs=[papers[x] for x in c["paper_ids"]]
            if len(refs)<2:raise ValueError("最终推荐至少需要两篇可追溯学术论文")
            items.append({**c,"papers":refs,"research_path":path,
                "machine_score":allowed[pid],"novelty_verified":False,
                "evidence_level":"bibliographic metadata and available abstract",
                "human_review":"pending"})
        return {"items":items,
                "selection_reason":text(data.get("selection_reason"),"selection_reason",900),
                "risks":string_list(data.get("risks",[]),"risks")}
    raise ValueError("无法识别的科研阶段")
