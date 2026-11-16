"""Cloudflare R2 S3-compatible storage adapter for research artifacts."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class R2Config:
    bucket: str
    endpoint: str
    access_key_id: str
    secret_access_key: str

    @classmethod
    def from_env(cls) -> "R2Config":
        keys = ("R2_BUCKET", "R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
        missing = [key for key in keys if not os.getenv(key)]
        if missing:
            raise RuntimeError("Missing R2 configuration: " + ", ".join(missing))
        endpoint = os.environ["R2_ENDPOINT"].rstrip("/")
        if not endpoint.startswith("https://") or not endpoint.endswith(".r2.cloudflarestorage.com"):
            raise ValueError("R2_ENDPOINT must be a Cloudflare R2 HTTPS S3 endpoint")
        return cls(
            bucket=os.environ["R2_BUCKET"],
            endpoint=endpoint,
            access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        )


def client(config: R2Config):
    """Create an authenticated R2 client. Credentials are never logged."""
    import boto3
    from botocore.config import Config
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
    )


def put_json_bytes(s3, bucket: str, key: str, payload: bytes) -> str:
    """Persist a JSON checkpoint and return its SHA256 checksum."""
    checksum = hashlib.sha256(payload).hexdigest()
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=payload,
        ContentType="application/json; charset=utf-8",
        Metadata={"sha256": checksum},
    )
    return checksum


def get_verified_bytes(s3, bucket: str, key: str, expected_sha256: str) -> bytes:
    """Retrieve object and independently verify integrity."""
    response = s3.get_object(Bucket=bucket, Key=key)
    payload = response["Body"].read()
    observed = hashlib.sha256(payload).hexdigest()
    if observed != expected_sha256:
        raise ValueError("R2 object integrity mismatch")
    return payload
