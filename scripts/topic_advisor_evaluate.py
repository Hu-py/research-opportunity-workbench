"""Run a fixed public/synthetic pilot; never reads production databases."""
import argparse
import hashlib
import json
from pathlib import Path
import httpx
from backend.topic_advisor import ExperimentModel, advise, artifacts, save, encode
from research_workbench.core import session_factory

CASES = [
    ("heat", "development", "城市热暴露与树冠公平", "urban tree canopy heat exposure inequality"),
    ("transit", "test", "公交可靠性与就业可达性", "public transport reliability employment accessibility"),
    ("flood", "held_out", "城市洪涝与基础设施韧性", "urban flood infrastructure resilience"),
]


def evidence(query):
    with httpx.Client(timeout=25, follow_redirects=False) as client:
        response = client.get("https://api.openalex.org/works", params={"search": query, "per-page": 5})
        response.raise_for_status()
        papers = []
        for x in response.json()["results"]:
            inverted = x.get("abstract_inverted_index") or {}
            words = {i: w for w, positions in inverted.items() for i in positions}
            papers.append({"id": x["id"], "title": x["title"], "doi": x.get("doi") or "",
                           "url": x["id"], "published": x.get("publication_date"),
                           "abstract": " ".join(words[i] for i in sorted(words))[:1800],
                           "evidence_status": "public_metadata_not_human_reviewed"})
        return papers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", type=int, default=1)
    parser.add_argument("--case", choices=["heat", "transit"])
    parser.add_argument("--skip-review", action="store_true")
    args = parser.parse_args()
    root = Path("data/topic-advisor")
    root.mkdir(parents=True, exist_ok=True)
    factory = session_factory("sqlite:///data/topic-advisor/experiments.db")
    model = ExperimentModel(factory, str(root / "experiment.lock"))
    for case, split, name, query in CASES:
        if split == "held_out":
            continue
        if args.case and case != args.case:
            continue
        contexts = [x for x in artifacts(factory, "context") if x["content"]["case"] == case]
        if contexts:
            context = contexts[0]["content"]
        else:
            context = {"case": case, "split": split, "material": "synthetic team; real public bibliography",
                       "line": {"id": case, "name": name, "problem": name, "keywords": []},
                       "goals": "发现具体、可证伪、可用公开数据初步验证的科学问题；团队擅长GIS和统计建模。",
                       "datasets": [], "team_achievements": [], "papers": evidence(query),
                       "availability": "no dataset access verified; no private team facts supplied"}
            save(factory, "context", context)
        for strategy in (("A", "B", "C") if args.revision == 1 else ("C",)):
            existing = [x for x in artifacts(factory, "result") if
                        x["content"]["case"] == case and x["content"]["strategy"] == strategy
                        and x["content"]["revision"] == args.revision]
            if existing:
                continue
            print(case, strategy, args.revision, flush=True)
            try:
                result = advise(model, context, strategy, args.revision)
                save(factory, "result", {"case": case, "strategy": strategy,
                                          "revision": args.revision, "result": result})
            except Exception as exc:
                save(factory, "failure", {"case": case, "strategy": strategy,
                                           "revision": args.revision, "error": type(exc).__name__})
                print("Failed:", type(exc).__name__, str(exc)[:220] if type(exc).__name__ in ("ModelCallError", "ValueError") else "", flush=True)
                recent = artifacts(factory, "model_call")[-3:]
                if len(recent) == 3 and all(x["content"]["status"] == "failed" for x in recent):
                    print("Circuit open: three consecutive provider failures; stopping paid calls", flush=True)
                    return
        results = [x for x in artifacts(factory, "result") if x["content"]["case"] == case]
        blinded = sorted(results, key=lambda x: hashlib.sha256(x["id"].encode()).hexdigest())
        submissions = [{"label": f"S{i}", "ideas": x["content"]["result"]["ideas"]}
                       for i, x in enumerate(blinded)]
        for reviewer in (() if args.skip_review else ("methods", "feasibility")):
            assessment = model.call(
                "独立盲评科研选题，不推测生成策略。输出 JSON reviews 数组，每项含 label、"
                "question_quality、novelty_potential、team_fit、data_feasibility、citation_reliability、"
                "diversity（各1-5分）、worth_review、defects、reason。保留分歧，不能认证创新性。",
                {"role": reviewer, "context": context, "submissions": submissions},
                model="deepseek-v4-pro", max_tokens=3000)
            save(factory, "assessment", {"case": case, "revision": args.revision,
                                         "reviewer": reviewer, "assessment": assessment,
                                         "mapping": {f"S{i}": x["id"] for i, x in enumerate(blinded)}})
    rows = artifacts(factory, "model_call")
    print(encode({"attempts": len(rows), "estimated_cny_upper": sum(
        r["content"].get("charged_bound", r["content"]["reservation"]) for r in rows)}))


if __name__ == "__main__":
    main()
