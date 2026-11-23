from datetime import timedelta

from research_workbench.core import session_factory
from backend.tasks import ResearchTask, claim, recover_stale_running, utc_now


def test_stale_running_tasks_are_requeued_but_recent_tasks_are_not(tmp_path):
    factory = session_factory("sqlite:///" + str(tmp_path / "worker-queue.db"))
    with factory() as db:
        now = utc_now()
        stale = ResearchTask(
            id="stale-task", kind="research_opportunity", query="stale",
            status="running", updated_at=now - timedelta(hours=2),
        )
        recent = ResearchTask(
            id="recent-task", kind="research_opportunity", query="recent",
            status="running", updated_at=now - timedelta(minutes=5),
        )
        db.add_all([stale, recent])
        db.commit()

        assert recover_stale_running(db, stale_after_seconds=3600) == 1
        db.refresh(stale)
        db.refresh(recent)
        assert stale.status == "queued"
        assert "requeued" in stale.error.lower()
        assert recent.status == "running"

        assert claim(db, stale.id) is True
        assert claim(db, stale.id) is False
        db.refresh(stale)
        assert stale.status == "running"
