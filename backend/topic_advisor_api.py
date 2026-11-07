"""Portfolio and explicit human decision memory using existing auth and database."""
from typing import Literal
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from backend.topic_advisor import TopicArtifact, artifacts, save


class Decision(BaseModel):
    result_id: str = Field(max_length=64)
    title: str = Field(min_length=1, max_length=300)
    action: Literal["accept", "modify", "reject", "defer"]
    reason: str = Field(min_length=10, max_length=3000)
    principle: str = Field(min_length=10, max_length=2000)


def mount(app, get_factory, require_actor, require_editor):
    @app.get("/api/topic-advisor/paper-understanding/examples", dependencies=[Depends(require_actor)])
    def reading_examples(target_doi: str = ""):
        from backend.paper_understanding import retrieve_cases
        return {"cases": retrieve_cases(target_doi, ["scientific_problem_reframing", "causal_boundary"]),
                "status": "development_exemplars_pending_passage_audit",
                "affects_recommendations": False}

    @app.get("/api/topic-advisor", dependencies=[Depends(require_actor)])
    def portfolio():
        factory = get_factory()
        return {"results": artifacts(factory, "result"), "contexts": artifacts(factory, "context"),
                "decisions": artifacts(factory, "decision"), "assessments": artifacts(factory, "assessment"),
                "runs": artifacts(factory, "run")}

    @app.post("/api/topic-advisor/feedback")
    def feedback(body: Decision, actor=Depends(require_editor)):
        factory = get_factory()
        with factory() as db:
            result = db.get(TopicArtifact, body.result_id)
            if not result or result.kind != "result":
                raise HTTPException(404, "选题版本不存在")
            import json
            titles = {x["title"] for x in json.loads(result.content)["result"]["ideas"]}
            if body.title not in titles:
                raise HTTPException(422, "选题不属于该版本")
        return {"id": save(factory, "decision", {**body.model_dump(),
                       "actor_id": getattr(actor, "id", "local-development"),
                       "source": "explicit_human_feedback", "confirmed": True,
                       "status": "human_decision_not_verified_scientific_fact"})}
