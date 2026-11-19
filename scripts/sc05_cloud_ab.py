"""Cloud-only SC05 A/B resume and R2 audit archival.

Uses the already-uploaded Owner-owned source and the existing saved pair.
Never uploads a PDF to GitHub and never prints credentials or private facts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import httpx

from backend.r2_storage import R2Config, client as r2_client, put_json_bytes

API_ROOT = "/api/personal-research/me/sc05"
DEFAULT_PAIR = "sc05pair_335281590c6d4d5f8fb5025de97a"
DEFAULT_SOURCE = "f8138694727ee27d4e399533311364eb137250d66b62d4b0f16d47d4c781a181"


def require_env(*names):
    missing = [x for x in names if not os.getenv(x, "").strip()]
    if missing:
        raise RuntimeError("Missing GitHub Actions secrets: " + ", ".join(missing))


def api_client():
    require_env("SC05_API_BASE_URL", "SC05_API_BEARER_TOKEN", "SC05_OWNER_SESSION")
    base = os.environ["SC05_API_BASE_URL"].rstrip("/")
    if not base.startswith("https://"):
        raise RuntimeError("SC05_API_BASE_URL must use HTTPS")
    return httpx.Client(
        base_url=base,
        follow_redirects=False,
        timeout=55,
        headers={
            "Authorization": "Bearer " + os.environ["SC05_API_BEARER_TOKEN"],
            "X-Research-Session": os.environ["SC05_OWNER_SESSION"],
        },
    )


def request(http, method, path, **kwargs):
    try:
        response = http.request(method, API_ROOT + path, **kwargs)
    except httpx.HTTPError as exc:
        raise RuntimeError("SC05 API network error: " + type(exc).__name__) from None
    if response.status_code >= 400:
        # Do not print returned response bodies (they may include private data).
        raise RuntimeError("SC05 API HTTP " + str(response.status_code) + " at " + method + " " + path.split("?")[0])
    return response.json()


def selected_pair(http, pair_id, expected_source):
    overview = request(http, "GET", "")
    runs = [x for x in overview.get("runs", []) if x.get("pair_id") == pair_id]
    if len(runs) != 2 or {x.get("variant") for x in runs} != {"science_gate_off", "science_gate_on"}:
        raise RuntimeError("Expected exact existing SC05 A/B pair not found; nothing started")
    cases = {x["id"]: x for x in overview.get("cases", [])}
    if len({x["case_id"] for x in runs}) != 1 or runs[0]["case_id"] not in cases:
        raise RuntimeError("Source case missing or mismatched")
    case = cases[runs[0]["case_id"]]
    if case.get("sha256") != expected_source:
        raise RuntimeError("Source paper SHA256 differs; refuse to run a different paper")
    return overview, case, {x["variant"]: x for x in runs}


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def archive(http, s3, bucket, prefix, run):
    run_id = run["id"]
    audit = request(http, "GET", "/runs/" + run_id + "/audit")
    if audit.get("id") != run_id or audit.get("source_sha") != prefix.split("/")[1]:
        raise RuntimeError("R2 archive source audit mismatch")
    count = len(audit.get("checkpoints", []))
    key = prefix + "/runs/" + run_id + "/checkpoints-" + str(count).zfill(3) + ".json"
    checksum = put_json_bytes(s3, bucket, key, json_bytes(audit))
    detail = request(http, "GET", "/runs/" + run_id)
    if detail.get("status") == "completed":
        report = detail.get("report_md") or ""
        if not report:
            raise RuntimeError("Run is complete but report is missing")
        s3.put_object(
            Bucket=bucket,
            Key=prefix + "/runs/" + run_id + "/report.md",
            Body=report.encode("utf-8"),
            ContentType="text/markdown; charset=utf-8",
            Metadata={"sha256": hashlib.sha256(report.encode("utf-8")).hexdigest()},
        )
    return {"id": run_id, "status": detail.get("status"), "stage": detail.get("stage"),
            "calls": detail.get("model_calls"), "checkpoints": count, "checkpoint_sha256": checksum}


def persist(http, s3, config, pair_id, case, variants):
    prefix = "sc05/" + case["sha256"] + "/" + pair_id
    rows = []
    for variant in ("science_gate_off", "science_gate_on"):
        rows.append(archive(http, s3, config.bucket, prefix, variants[variant]))
    manifest = {
        "pair_id": pair_id, "source_sha256": case["sha256"],
        "archived_at_utc": datetime.now(timezone.utc).isoformat(),
        "runs": rows,
    }
    put_json_bytes(s3, config.bucket, prefix + "/manifest.json", json_bytes(manifest))
    print("Private R2 checkpoint archive verified:", [(x["id"], x["status"], x["checkpoints"]) for x in rows])
    return manifest


def run_one(http, s3, config, pair_id, source, variant, max_wait_seconds, poll_seconds):
    overview, case, runs = selected_pair(http, pair_id, source)
    run = runs[variant]
    current = request(http, "GET", "/runs/" + run["id"])
    if current["status"] == "completed":
        print("Already complete; no new paid call:", variant)
        persist(http, s3, config, pair_id, case, runs)
        return
    if current["status"] == "failed":
        repair = request(http, "GET", "/runs/" + run["id"] + "/repair-check")
        if not repair.get("ready"):
            raise RuntimeError("Saved checkpoint is not eligible for safe replay; stopped before any paid call")
        print("Verified safe checkpoint replay:", variant, "existing calls:", current.get("model_calls"))
    if current["status"] in ("prepared", "failed"):
        print("Starting authorized existing run:", variant, run["id"])
        request(http, "POST", "/runs/" + run["id"] + "/start",
                json={"acknowledge_external_model": True})
    elif current["status"] not in ("queued", "running"):
        raise RuntimeError("Unsupported status: " + str(current["status"]))
    deadline = time.monotonic() + max_wait_seconds
    last_count = -1
    while time.monotonic() < deadline:
        status = request(http, "GET", "/runs/" + run["id"])
        audit = request(http, "GET", "/runs/" + run["id"] + "/audit")
        count = len(audit.get("checkpoints", []))
        if count != last_count or status["status"] in ("completed", "failed"):
            _, updated_case, updated_runs = selected_pair(http, pair_id, source)
            persist(http, s3, config, pair_id, updated_case, updated_runs)
            print("SC05 stage:", variant, status["status"], "calls:", status.get("model_calls"), "checkpoints:", count)
            last_count = count
        if status["status"] == "completed":
            return
        if status["status"] == "failed":
            raise RuntimeError("SC05 run failed at stage " + str(status.get("stage")) +
                               "; error type logged in Owner dashboard, B will not start")
        time.sleep(poll_seconds)
    raise RuntimeError("Timed out while waiting; run may still be active; do not re-launch blindly")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preflight", "run"), default="preflight")
    parser.add_argument("--pair-id", default=DEFAULT_PAIR)
    parser.add_argument("--source-sha256", default=DEFAULT_SOURCE)
    parser.add_argument("--acknowledge-paid", action="store_true")
    parser.add_argument("--max-wait-seconds", type=int, default=1500)
    parser.add_argument("--poll-seconds", type=int, default=15)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"sc05pair_[a-f0-9]{28}", args.pair_id) or not re.fullmatch(r"[a-f0-9]{64}", args.source_sha256):
        raise RuntimeError("Invalid pair ID or paper SHA")
    if args.mode == "run" and not args.acknowledge_paid:
        raise RuntimeError("Paid run requires explicit --acknowledge-paid")
    config = R2Config.from_env()
    s3 = r2_client(config)
    with api_client() as http:
        overview, case, runs = selected_pair(http, args.pair_id, args.source_sha256)
        # Save paid pre-existing checkpoint before trying any new model calls.
        persist(http, s3, config, args.pair_id, case, runs)
        print("Existing pair verified:", args.pair_id, "source:", case["sha256"][:16],
              "budget:", {k: v for k, v in (overview.get("budget") or {}).items()
                          if isinstance(v, (int, float, bool, str))})
        if args.mode == "preflight":
            print("PREFLIGHT PASSED: no DeepSeek calls requested")
            return 0
        run_one(http, s3, config, args.pair_id, args.source_sha256,
                "science_gate_off", args.max_wait_seconds, args.poll_seconds)
        run_one(http, s3, config, args.pair_id, args.source_sha256,
                "science_gate_on", args.max_wait_seconds, args.poll_seconds)
        overview, case, runs = selected_pair(http, args.pair_id, args.source_sha256)
        persist(http, s3, config, args.pair_id, case, runs)
        print("SC05 REAL PAIR COMPLETED; blind scoring remains a separate human review.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError) as exc:
        print("SC05 CLOUD STOP:", str(exc))
        sys.exit(2)
