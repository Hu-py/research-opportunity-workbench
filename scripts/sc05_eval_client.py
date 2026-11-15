"""Run SC05 A/B from a trusted operator machine, without a new frontend.

Credential inputs come only from the environment, never CLI flags or logs:
  SC05_API_BASE_URL=<isolated Render URL>
  SC05_API_BEARER_TOKEN=<service bearer token>
  SC05_OWNER_SESSION=<short-lived Owner session token>

Prepare without spending:
  python -m scripts.sc05_eval_client --pdf ./published.pdf --out ./sc05_ab
Authorize actual DeepSeek calls:
  python -m scripts.sc05_eval_client --pair-id sc05pair_... \
      --out ./sc05_ab --authorize-paid --wait

The CLI intentionally cannot bypass the existing team Owner session. Never
paste any of the tokens into chat, GitHub issues, or a public log.
"""
from __future__ import annotations
import argparse
import json
import os
import time
from pathlib import Path

import httpx

PATH="/api/personal-research/me/sc05"


def client():
    base=os.getenv("SC05_API_BASE_URL","").strip().rstrip("/")
    token=os.getenv("SC05_API_BEARER_TOKEN","").strip()
    session=os.getenv("SC05_OWNER_SESSION","").strip()
    if not base.startswith("https://"):
        raise ValueError("SC05_API_BASE_URL must be an HTTPS service URL")
    if not token or not session:
        raise ValueError("Set SC05_API_BEARER_TOKEN and SC05_OWNER_SESSION securely")
    return httpx.Client(base_url=base,follow_redirects=False,timeout=120,
            headers={"Authorization":"Bearer "+token,"X-Research-Session":session})


def request(c,method,path,**kwargs):
    response=c.request(method,PATH+path,**kwargs)
    if response.status_code>=400:
        raise RuntimeError("SC05 operation failed (HTTP "+
                           str(response.status_code)+")")
    return response.json()


def main(argv=None):
    parser=argparse.ArgumentParser(description="SC05 isolated authenticated research A/B")
    parser.add_argument("--pdf",type=Path,help="Published PDF to upload once")
    parser.add_argument("--pair-id",help="Continue existing pair instead of uploading again")
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--authorize-paid",action="store_true",
        help="Explicitly permit actual billed DeepSeek API calls")
    parser.add_argument("--wait",action="store_true",
        help="Poll until both runs finish; terminal statuses are printed")
    parser.add_argument("--max-wait-seconds",type=int,default=1800)
    args=parser.parse_args(argv)
    if bool(args.pdf)==bool(args.pair_id):
        parser.error("Pass exactly one of --pdf or --pair-id")
    args.out.mkdir(parents=True,exist_ok=True,mode=0o700)
    with client() as c:
        if args.pdf:
            if not args.pdf.is_file() or args.pdf.suffix.lower()!=".pdf":
                parser.error("--pdf must point to an existing PDF file")
            if args.pdf.stat().st_size>32000000:
                parser.error("PDF is larger than 32 MB")
            case=request(c,"POST","/cases/pdf",
                headers={"Content-Type":"application/pdf",
                         "X-Research-Paper-Title":args.pdf.stem[:280]},
                content=args.pdf.read_bytes())
            pair=request(c,"POST","/cases/"+case["id"]+"/ab")
            pair_id=pair["pair_id"]
            (args.out/"sc05_pair_ids.json").write_text(
                json.dumps({"case_id":case["id"],"pair_id":pair_id,
                            "runs":[x["id"] for x in pair["runs"]]},indent=2))
            print("Created paired experiment:",pair_id)
        else:
            pair_id=args.pair_id
        overview=request(c,"GET","")
        runs=[r for r in overview["runs"] if r["pair_id"]==pair_id]
        if len(runs)!=2:raise RuntimeError("No matching two-run pair")
        # Never start the gate-on variant until shared evidence was frozen.
        audit_views={r["id"]:request(c,"GET","/runs/"+r["id"]+"/audit") for r in runs}
        ordered=sorted(runs,key=lambda r:0 if audit_views[r["id"]]["variant"]=="science_gate_off" else 1)
        if not args.authorize_paid:
            print("Prepared; no paid requests triggered. Set --authorize-paid to run.")
            return 0
        for item in ordered:
            run_id=item["id"]
            current=request(c,"GET","/runs/"+run_id)
            if current["status"]!="completed":
                if current["status"] in ("prepared","failed"):
                    request(c,"POST","/runs/"+run_id+"/start",
                            json={"acknowledge_external_model":True})
                if args.wait:
                    deadline=time.monotonic()+args.max_wait_seconds
                    while time.monotonic()<deadline:
                        current=request(c,"GET","/runs/"+run_id)
                        if current["status"] in ("completed","failed"):break
                        time.sleep(10)
                    if current["status"]!="completed":
                        print("Run unfinished:",run_id,current["status"])
                        # Do not start B with incomplete or failed A.
                        return 2
            if current["status"]=="completed":
                (args.out/(run_id+"_report.md")).write_text(
                    current["report_md"],encoding="utf-8")
                raw=request(c,"GET","/runs/"+run_id+"/audit")
                (args.out/(run_id+"_audit.json")).write_text(
                    json.dumps(raw,ensure_ascii=False,indent=2),encoding="utf-8")
                print("Saved completed:",run_id)
        blind=request(c,"GET","/pairs/"+pair_id+"/blind")
        if blind["ready"]:
            for item in blind["blind_reports"]:
                (args.out/("blind_"+item["label"]+".md")).write_text(
                    item["report_md"],encoding="utf-8")
            print("Blinded A/B reports ready, pair:",pair_id)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
