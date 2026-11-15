"""Read-only, metadata-only inventory for privately stored SC05 artifacts.

Uses R2 credentials in GitHub Actions. No object bodies or secrets are read
or printed. Public CI logs show only counts and completion booleans.
"""
from __future__ import annotations
from backend.r2_storage import R2Config, client

SOURCE="f8138694727ee27d4e399533311364eb137250d66b62d4b0f16d47d4c781a181"
RUNS={
    "A":"sc05run_1380a7cde2354fc387d87ded2444",
    "B":"sc05run_527287b83f3846b4b234f6a9512a",
}

def main():
    cfg=R2Config.from_env()
    s3=client(cfg)
    for label,run_id in RUNS.items():
        prefix=f"sc05/{SOURCE}/{run_id}/"
        response=s3.list_objects_v2(Bucket=cfg.bucket, Prefix=prefix, MaxKeys=1000)
        keys=[x["Key"][len(prefix):] for x in response.get("Contents",[])]
        print(f"SC05 {label} R2 INVENTORY: objects={len(keys)} "
              f"checkpoint_snapshots={sum(k.startswith('checkpoints/') for k in keys)} "
              f"source_present={'source_pages.json' in keys} "
              f"report_present={'report.md' in keys} "
              f"manifest_present={'manifest.json' in keys}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())

# Manual verification snapshot 2 after Owner-delegated Render execution.
