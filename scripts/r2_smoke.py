"""Ephemeral R2 read/write smoke test. Does not touch research data."""
from __future__ import annotations
import json
import sys
import uuid

from backend.r2_storage import R2Config, client, put_json_bytes, get_verified_bytes


def main() -> int:
    try:
        config = R2Config.from_env()
    except (RuntimeError, ValueError) as exc:
        print("R2 PREFLIGHT FAILED:", exc)
        return 2

    s3 = client(config)
    key = f"_smoke/{uuid.uuid4().hex}.json"
    payload = json.dumps({"test": "r2_roundtrip", "nonce": uuid.uuid4().hex}).encode()
    uploaded = False
    try:
        checksum = put_json_bytes(s3, config.bucket, key, payload)
        uploaded = True
        assert get_verified_bytes(s3, config.bucket, key, checksum) == payload
        print("R2 ROUNDTRIP PASSED: upload, download, SHA256 verification")
        return 0
    except Exception as exc:
        # Never print full SDK errors: request metadata could reveal account details.
        print("R2 ROUNDTRIP FAILED:", type(exc).__name__)
        return 1
    finally:
        if uploaded:
            try:
                s3.delete_object(Bucket=config.bucket, Key=key)
                print("R2 smoke object cleaned up")
            except Exception:
                print("WARNING: cleanup failed; remove the _smoke object manually")


if __name__ == "__main__":
    sys.exit(main())
