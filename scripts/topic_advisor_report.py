"""Public synthetic-pilot report and explicit local-only portfolio copy."""
import argparse
from backend.topic_advisor import TopicArtifact, artifacts, encode
from research_workbench.core import session_factory


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--portfolio", action="store_true")
    args = p.parse_args()
    source = session_factory("sqlite:///data/topic-advisor/experiments.db")
    calls = artifacts(source, "model_call")
    totals = {"attempts": len(calls), "input_tokens_observed": 0, "output_tokens_observed": 0,
              "estimated_cny_including_unknown_reservations": 0, "unknown_usage_calls": 0}
    for r in calls:
        c = r["content"]
        usage = c.get("usage")
        if usage is None:
            totals["unknown_usage_calls"] += 1
        totals["input_tokens_observed"] += (usage or {}).get("input_tokens", 0)
        totals["output_tokens_observed"] += (usage or {}).get("output_tokens", 0)
        totals["estimated_cny_including_unknown_reservations"] += c.get("charged_bound", c["reservation"])
    report = {"usage": totals, **{kind: artifacts(source, kind) for kind in
              ("context", "result", "assessment", "failure")}}
    # This export is restricted to the explicitly synthetic/public fixture runner.
    if any(x["content"].get("material") != "synthetic team; real public bibliography" for x in report["context"]):
        raise ValueError("Refusing to export non-public experiment context")
    print(encode(report))
    if args.portfolio:
        target = session_factory("sqlite:///data/topic-advisor/portfolio.db")
        with target() as db:
            for kind in ("context", "result", "assessment"):
                for row in report[kind]:
                    if db.get(TopicArtifact, row["id"]) is None:
                        db.add(TopicArtifact(id=row["id"], kind=kind, content=encode(row["content"]),
                                             created_at=row["created_at"]))
            db.commit()


if __name__ == "__main__":
    main()
