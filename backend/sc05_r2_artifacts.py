"""Private R2 archival for SC05 after PostgreSQL commits.

Database is the source of truth: an R2 outage must never cause another
paid model request. The worker alone receives R2 credentials.
"""
from __future__ import annotations

import hashlib
import json

from backend.r2_storage import R2Config, client as r2_client, put_json_bytes


def _json_bytes(obj: object) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def archive_run(factory, run_id: str) -> dict:
    """Write source pages, stage checkpoints and final report to a private R2 bucket.

    Caller must be an authenticated, Owner-authorized task executor. This
    method intentionally has no HTTP endpoint and prints no source content.
    """
    # Lazy import keeps the public API independent of the boto3 package.
    from backend.sc05_eval_api import SC05Case, SC05Run, load
    with factory() as db:
        run = db.get(SC05Run, run_id)
        if run is None:
            raise RuntimeError("SC05 run not found")
        paper = db.get(SC05Case, run.case_id)
        if paper is None:
            raise RuntimeError("SC05 paper not found")
        source_sha = paper.source_sha
        pages = load(paper.pages_json, {})
        checkpoints = load(run.checkpoints_json, [])
        if not isinstance(checkpoints, list):
            raise RuntimeError("Malformed SC05 checkpoint data")
        metadata = {
            "run_id": run.id,
            "pair_id": run.pair_id,
            "variant": run.variant,
            "source_sha256": source_sha,
            "pipeline_sha256": run.pipeline_sha,
            "status": run.status,
            "stage": run.stage,
            "model_calls": run.calls,
            "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens,
            "checkpoint_count": len(checkpoints),
        }
        report = run.report_md if run.status == "completed" else ""
        result = load(run.result_json, {}) if run.status == "completed" else None
    config = R2Config.from_env()
    s3 = r2_client(config)
    prefix = f"sc05/{source_sha}/{run_id}"
    # Storage is private; source-page text has the same confidentiality as PDF.
    source_key = prefix + "/source_pages.json"
    source_digest = put_json_bytes(s3, config.bucket, source_key, _json_bytes(pages))
    checkpoint_doc = {"metadata": metadata, "checkpoints": checkpoints}
    if checkpoints:
        snapshot_key = prefix + f"/checkpoints/stage-{len(checkpoints):03d}.json"
        saved_digest = put_json_bytes(s3, config.bucket, snapshot_key, _json_bytes(checkpoint_doc))
    else:
        saved_digest = ""
    if report:
        payload = report.encode("utf-8")
        s3.put_object(
            Bucket=config.bucket,
            Key=prefix + "/report.md",
            Body=payload,
            ContentType="text/markdown; charset=utf-8",
            Metadata={"sha256": hashlib.sha256(payload).hexdigest()},
        )
        put_json_bytes(s3, config.bucket, prefix + "/result.json", _json_bytes(result))
    manifest = {
        **metadata,
        "source_pages_sha256": source_digest,
        "checkpoints_sha256": saved_digest,
        "report_saved": bool(report),
        "source_is_extracted_pages_not_pdf": True,
    }
    put_json_bytes(s3, config.bucket, prefix + "/manifest.json", _json_bytes(manifest))
    return {"run_id": run_id, "checkpoint_count": len(checkpoints), "report_saved": bool(report)}
