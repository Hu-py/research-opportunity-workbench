"""Zero-cost SC05 Render queue worker contract tests.

They use only SQLite and synthetic research rows. They never contact DeepSeek
or Cloudflare. The live Render probe tests the same PostgreSQL claim path.
"""
import os

from backend.sc05_worker import (
    SC05WorkerProbe, SC05DelegatedAuthorization,
    execute_once, execute_probe_once, worker_status,
)
from backend.sc05_eval_api import SC05Case, SC05Run
from backend.team import create_member
from research_workbench.core import session_factory


def workspace(tmp_path):
    factory=session_factory("sqlite:///"+str(tmp_path/"sc05-worker-test.db"))
    with factory() as db:
        user=create_member(
            db,"owner@unit-test.invalid","Owner",
            "offline-worker-password-1234",role="admin",initial=True,
        )
        doc=SC05Case(
            id="sc05case_"+"a"*28,member_id=user.id,
            title="Synthetic research source",pages_json='{"page_01":"test"}',
            source_sha="a"*64,source_type="uploaded_pdf",
        )
        db.add(doc)
        for n in ("1","2"):
            db.add(SC05Run(
                id="sc05run_"+n*28,member_id=user.id,case_id=doc.id,
                pair_id="sc05pair_"+"c"*28,variant="science_gate_off",
                pipeline_sha="0"*64,status="queued",
            ))
        db.commit()
        return factory,user.id


def test_synthetic_worker_probe_is_persistent_without_llm(tmp_path):
    factory,_=workspace(tmp_path)
    with factory() as db:
        db.add(SC05WorkerProbe(id="sc05probe_20261116_cloud_test",status="queued"))
        db.commit()
    assert execute_probe_once(factory,require_pg=False)=="sc05probe_20261116_cloud_test"
    assert execute_probe_once(factory,require_pg=False) is None
    status=worker_status(factory)
    assert status["recent_probes"][0]["status"]=="completed"
    assert status["recent_probes"][0]["completed_at"]
    assert status["approved_queued_dispatches"]==0


def test_worker_claims_only_owner_approved_dispatch_and_never_replays(tmp_path,monkeypatch):
    factory,owner_id=workspace(tmp_path)
    import backend.sc05_worker as worker
    ids=[]
    def fake_execute(_factory,run_id,*,claimed_by_worker):
        assert claimed_by_worker is True
        ids.append(run_id)
        with _factory() as db:
            row=db.get(SC05Run,run_id)
            assert row.status=="claimed"
            row.status="completed"
            row.stage="complete"
            row.calls=0
            db.commit()
    monkeypatch.setattr(worker,"execute",fake_execute)
    # A historical queued job is NOT enough: no delegated authorization.
    assert execute_once(factory,delegated_only=True,require_pg=False) is False
    with factory() as db:
        db.add(SC05DelegatedAuthorization(
            run_id="sc05run_"+"2"*28,member_id=owner_id,status="approved"
        ))
        db.commit()
    assert execute_once(factory,delegated_only=True,require_pg=False) is True
    assert ids==["sc05run_"+"2"*28]
    assert execute_once(factory,delegated_only=True,require_pg=False) is False
    with factory() as db:
        assert db.get(SC05Run,"sc05run_"+"1"*28).status=="queued"
        assert db.get(SC05Run,"sc05run_"+"2"*28).status=="completed"
        assert db.get(SC05DelegatedAuthorization,"sc05run_"+"2"*28).status=="completed"


def test_ambiguous_running_job_blocks_new_claims(tmp_path,monkeypatch):
    factory,owner_id=workspace(tmp_path)
    with factory() as db:
        db.get(SC05Run,"sc05run_"+"1"*28).status="running"
        db.add(SC05DelegatedAuthorization(
            run_id="sc05run_"+"2"*28,member_id=owner_id,status="approved"
        ))
        db.commit()
    # Never retry another paid stage while an interrupted call is ambiguous.
    assert execute_once(factory,delegated_only=True,require_pg=False) is False
    with factory() as db:
        assert db.get(SC05DelegatedAuthorization,"sc05run_"+"2"*28).status=="approved"
