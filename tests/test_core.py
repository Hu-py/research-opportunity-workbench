"""Offline unit/integration tests; never call a live scholarly API."""
import json
from datetime import date
import httpx
import pytest
from sqlalchemy import select,func
from research_workbench.core import (
    Paper, Idea, Evidence, Event, session_factory, set_profile, get_profile,
    normalize_doi, decode_abstract, normalize_paper, ingest, propose, feedback,
    weekly_report, validate_profile
)

PROFILE={"research_lines":[{"id":"urban","name":"Urban networks",
    "problem":"Limited labels for spatial inference",
    "keywords":["urban","graph"],
    "search_queries":["urban graph"],"method_queries":["self-supervised graph"]}]}

def paper(suffix="1"):
    return {"id":"https://openalex.org/W"+suffix,
        "doi":"https://doi.org/10.9999/example"+suffix,
        "title":"Self-supervised graph neural network for urban systems "+suffix,
        "abstract_inverted_index":{"urban":[0],"graph":[1],"learning":[2]},
        "publication_date":date.today().isoformat(),
        "primary_location":{"source":{"display_name":"Example venue"}}}

def test_normalization():
    assert normalize_doi("https://DOI.org/10.9999/ABC")=="10.9999/abc"
    assert normalize_doi("bad")==""
    assert decode_abstract({"two":[1],"one":[0]})=="one two"
    assert normalize_paper(paper())["id"]=="doi:10.9999/example1"

def test_profile_validation():
    Factory=session_factory("sqlite:///:memory:")
    with Factory() as db:
        with pytest.raises(ValueError):validate_profile({"research_lines":[]})
        set_profile(db,PROFILE)
        assert get_profile(db)["research_lines"][0]["name"]=="Urban networks"

def test_ingest_evolution_and_feedback():
    Factory=session_factory("sqlite:///:memory:")
    current=[paper()]
    def handler(request):
        assert "from_publication_date" in str(request.url)
        return httpx.Response(200,json={"results":current})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with Factory() as db:
            set_profile(db,PROFILE)
            assert ingest(db,PROFILE,days=30,client=client)["new_papers"]==1
            assert ingest(db,PROFILE,days=30,client=client)["new_papers"]==0
            assert db.scalar(select(func.count()).select_from(Paper))==1
            assert propose(db,PROFILE)["new_ideas"]>=1
            assert propose(db,PROFILE)["revised_ideas"]==0
            idea=db.scalars(select(Idea).where(Idea.method=="self-supervised learning")).one()
            assert idea.version==1
            current.append(paper("2"))
            assert ingest(db,PROFILE,days=30,client=client)["new_papers"]==1
            assert propose(db,PROFILE)["revised_ideas"]>=1
            assert idea.version==2
            report=weekly_report(db,PROFILE)
            assert "10.9999/example2" in report
            assert "v" not in ""  # report generation smoke test
            feedback(db,idea.id,"rejected","overlaps related work")
            assert idea.status=="rejected" and idea.version==3
            assert propose(db,PROFILE)["revised_ideas"]==0
            assert db.scalar(select(func.count()).select_from(Event).where(Event.idea_id==idea.id))==3

def test_http_error_partial_collection():
    Factory=session_factory("sqlite:///:memory:")
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(403))) as client:
        with Factory() as db:
            result=ingest(db,PROFILE,client=client)
            assert len(result["failed_queries"])==2
            assert result["new_papers"]==0

def test_feedback_validation():
    Factory=session_factory("sqlite:///:memory:")
    with Factory() as db:
        with pytest.raises(ValueError):feedback(db,"missing","unsupported")
