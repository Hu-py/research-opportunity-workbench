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
    # Inspect ONLY schema classification labels in the last saved A checkpoint.
    # The source PDF, excerpts, prompts and diagnostic narrative remain private.
    import hashlib
    import json
    import re
    a_prefix=f"sc05/{SOURCE}/{RUNS['A']}/checkpoints/"
    listing=s3.list_objects_v2(Bucket=cfg.bucket, Prefix=a_prefix, MaxKeys=1000)
    keys=sorted(x["Key"] for x in listing.get("Contents",[]) if x["Key"].endswith(".json"))
    if keys:
        document=json.loads(s3.get_object(Bucket=cfg.bucket,Key=keys[-1])["Body"].read())
        checkpoints=document.get("checkpoints",[])
        if checkpoints:
            last=checkpoints[-1]
            stage=str(last.get("stage",""))[:40]
            print(f"SC05 A LATEST SAVED STAGE: {stage} (count={len(checkpoints)})")
            if stage=="diagnosis":
                data=last.get("response",{})
                allowed_status={"observed","hypothesis","unknown"}
                allowed_cls={"coverage","measurement","validation","method",
                             "interpretation","identifiability","resource","other"}
                allowed_conf={"low","medium","high"}
                def safe(v):
                    txt=v if isinstance(v,str) else type(v).__name__
                    if 0<len(txt)<=35 and all(c.isalnum() or c in " _-" for c in txt):
                        return txt
                    return "hash-"+hashlib.sha256(txt.encode()).hexdigest()[:8]
                for i,item in enumerate(data.get("diagnoses",[])[:12]):
                    if not isinstance(item,dict):
                        print(f"diagnosis #{i+1}: nonobject");continue
                    labels=(("epistemic_status",allowed_status),
                            ("issue_class",allowed_cls),
                            ("confidence",allowed_conf))
                    wrong=[(field,safe(item.get(field))) for field,accepted in labels
                           if item.get(field) not in accepted]
                    if wrong:
                        print(f"diagnosis #{i+1} invalid labels: {wrong}")
    return 0

if __name__=="__main__":
    raise SystemExit(main())

# Manual verification snapshot 2 after Owner-delegated Render execution.

# Post-diagnosis-resume verification snapshot.

# Model stage progression check, no object bodies logged.
