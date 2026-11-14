"""Isolated PostgreSQL-backed Development Studio end-to-end startup probe.

Uses the existing Render TEST database, but creates and selects a dedicated
Postgres schema. No secret, session token, password, or prompt is printed.
Never run this against a different database or production environment.
"""
from __future__ import annotations

import json
import os
import secrets
from urllib.parse import urlsplit

from sqlalchemy import create_engine, text

SCHEMA = "atlas_devstudio_e2e_20261114"
EXPECTED_DATABASE = "research_atlas_test_db"


def main() -> int:
    url = os.getenv("DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgresql+psycopg://", "postgres://")):
        raise RuntimeError("Refusing test: a PostgreSQL DATABASE_URL is required")
    database_name = urlsplit(url).path.removeprefix("/")
    if database_name != EXPECTED_DATABASE:
        raise RuntimeError("Refusing test: database is not the approved test database")
    if os.getenv("DEVSTUDIO_E2E_ISOLATED", "") != "1":
        raise RuntimeError("Refusing test: explicit isolation flag missing")
    if os.getenv("TEAM_AUTH_ENABLED", "").lower() not in ("true", "1"):
        raise RuntimeError("Refusing test: TEAM_AUTH_ENABLED must be true")
    if not os.getenv("API_BEARER_TOKEN", ""):
        raise RuntimeError("Refusing test: API bearer token is required")

    # CREATE SCHEMA changes metadata only in the preapproved TEST database.
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    engine.dispose()

    # libpq honors PGOPTIONS for every subsequent SQLAlchemy/psycopg session.
    os.environ["PGOPTIONS"] = "-c search_path=" + SCHEMA

    from fastapi.testclient import TestClient
    from research_workbench.core import session_factory
    from backend.team import create_member
    import backend.api as api

    factory = session_factory()
    with factory() as session:
        actual_schema = session.execute(text("SELECT current_schema()")).scalar_one()
        if actual_schema != SCHEMA:
            raise RuntimeError("Refusing test: PostgreSQL search_path is not isolated")
        # On Render instance restarts, never create another initial team.
        # Validate the previously committed E2E row instead of mutating it.
        persisted = session.execute(text(
            "SELECT count(*) FROM devstudio_experiments "
            "WHERE title LIKE 'E2E database write-read verification %'"
        )).scalar_one()
        if persisted:
            print(json.dumps({
                "type": "devstudio_isolated_postgres_e2e",
                "schema": SCHEMA,
                "result": "PASS_RESTART",
                "checks": ["schema_isolation", "persisted_verified_experiment"],
            }))
            return 0
        run_suffix = secrets.token_hex(7)
        admin_email = "devstudio-e2e-admin-" + run_suffix + "@example.invalid"
        member_email = "devstudio-e2e-editor-" + run_suffix + "@example.invalid"
        viewer_email = "devstudio-e2e-viewer-" + run_suffix + "@example.invalid"
        # Persist credentials only as hashes; plaintext passwords stay in process memory.
        admin_password = secrets.token_urlsafe(30)
        member_password = secrets.token_urlsafe(30)
        viewer_password = secrets.token_urlsafe(30)
        for email, display, password, role in (
            (admin_email, "E2E Admin", admin_password, "admin"),
            (member_email, "E2E Editor", member_password, "researcher"),
            (viewer_email, "E2E Viewer", viewer_password, "viewer"),
        ):
            create_member(session, email, display, password, role=role, initial=(role=="admin"))

    def headers(token=""):
        return {
            "Authorization": "Bearer " + os.environ["API_BEARER_TOKEN"],
            **({"X-Research-Session": token} if token else {}),
        }

    def signin(client, email, password):
        response = client.post("/api/auth/login", headers=headers(),
                               json={"email": email, "password": password})
        if response.status_code != 200:
            raise RuntimeError("Smoke login failed: HTTP " + str(response.status_code))
        return response.json()["token"]

    with TestClient(api.app) as client:
        admin = signin(client, admin_email, admin_password)
        editor = signin(client, member_email, member_password)
        viewer = signin(client, viewer_email, viewer_password)
        unauth = client.get("/api/devstudio/experiments", headers=headers())
        assert unauth.status_code == 401, "missing session must be denied"
        denied = client.post("/api/devstudio/experiments", headers=headers(viewer), json={
            "module_id": "PLATFORM", "title": "Unauthorized E2E write",
            "hypothesis": "Viewer should never be able to create an experiment."
        })
        assert denied.status_code == 403, "viewer write must be denied"

        title = "E2E database write-read verification " + secrets.token_hex(5)
        payload = {"module_id": "PLATFORM", "title": title,
                   "hypothesis": "An authorized editor can persist an experiment in isolated PostgreSQL.",
                   "baseline": "No prior persistent E2E run",
                   "input_snapshot_ref": "experiment/devstudio-postgres-e2e-20261114",
                   "metrics": ["database_roundtrip", "auth_denial", "run_evaluation"]}
        created = client.post("/api/devstudio/experiments", headers=headers(editor), json=payload)
        assert created.status_code == 201, "create failed HTTP " + str(created.status_code)
        exp_id = created.json()["id"]

        # Subsequent requests and a separate SQL session prove DB persistence.
        response = client.get("/api/devstudio/experiments", headers=headers(viewer))
        assert response.status_code == 200
        assert any(x["id"] == exp_id and x["title"] == title for x in response.json()["items"])
        with factory() as session:
            assert session.execute(text(
                "SELECT count(*) FROM devstudio_experiments WHERE id=:id"
            ), {"id": exp_id}).scalar_one() == 1

        run = client.post("/api/devstudio/experiments/" + exp_id + "/runs",
                          headers=headers(editor), json={
                              "kind": "github_actions",
                              "external_url": "https://github.com/Hu-py/research-opportunity-workbench/actions/runs/43572907443",
                              "note": "Code CI reference only. Does not independently verify DB execution.",
                          })
        assert run.status_code == 201, "run reference failed HTTP " + str(run.status_code)
        assert run.json()["status"] == "unverified"
        run_id = run.json()["id"]

        reviewed = client.post("/api/devstudio/runs/" + run_id + "/evaluations",
                               headers=headers(editor), json={
                                   "rubric_version": "devstudio-db-e2e-v1",
                                   "scores": {"database_roundtrip": 5, "auth_denial": 5},
                                   "limitations": "Isolated test schema. CI URL is a code reference only.",
                               })
        assert reviewed.status_code == 201
        assert client.get("/api/devstudio/runs/" + run_id + "/evaluations",
                          headers=headers(viewer)).json()["items"]

        lineage = client.get("/api/devstudio/lineage/PLATFORM", headers=headers(admin))
        assert lineage.status_code == 200
        assert any(x["id"] == exp_id for x in lineage.json()["experiments"])
        assert any(x["id"] == run_id for x in lineage.json()["runs"])
        assert client.get("/api/team/audit", headers=headers(admin)).status_code == 200

    print(json.dumps({
        "type": "devstudio_isolated_postgres_e2e",
        "schema": SCHEMA,
        "result": "PASS",
        "checks": ["schema_isolation", "team_login", "unauthorized_401",
                   "viewer_write_403", "experiment_create_201",
                   "cross_request_read", "separate_sql_session_read",
                   "run_link_unverified", "evaluation_read", "module_lineage", "audit_access"],
    }))
    return 0


if __name__ == "__main__":
    if main() == 0:
        # Keep PGOPTIONS in the same Python process so the server, not just
        # the startup probe, remains pinned to the isolated test schema.
        import uvicorn
        uvicorn.run("backend.api:app", host="0.0.0.0", port=8000)
