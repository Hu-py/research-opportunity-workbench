"""CLI for onboarding, ingestion, weekly reporting, and status updates."""
import argparse
import json
import os
from pathlib import Path
from .core import session_factory, set_profile, get_profile, ingest, propose, feedback, weekly_report
from backend.interests import ingest_interests  # register interests before Base.create_all

def main(argv=None):
    parser=argparse.ArgumentParser(prog="research-wb")
    sub=parser.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("profile-import")
    p.add_argument("path")
    p=sub.add_parser("ingest")
    p.add_argument("--days",type=int,default=14)
    p.add_argument("--per-query",type=int,default=15)
    sub.add_parser("ideate")
    p=sub.add_parser("feedback")
    p.add_argument("idea_id");p.add_argument("status");p.add_argument("--note",default="")
    p=sub.add_parser("weekly")
    p.add_argument("--days",type=int,default=14)
    p.add_argument("--email",action="store_true")
    args=parser.parse_args(argv)
    if os.getenv("GITHUB_ACTIONS")=="true" and not os.getenv("DATABASE_URL"):
        parser.error("GitHub Actions requires a persistent DATABASE_URL")
    Factory=session_factory()
    with Factory() as db:
        if args.cmd=="profile-import":
            set_profile(db,json.loads(Path(args.path).read_text(encoding="utf-8")))
            print("Research profile saved in database")
            return 0
        profile=get_profile(db)
        if not profile:parser.error("No research profile: run profile-import first")
        if args.cmd=="ingest":print(json.dumps(ingest(db,profile,days=args.days,limit=args.per_query)))
        elif args.cmd=="ideate":print(json.dumps(propose(db,profile)))
        elif args.cmd=="feedback":feedback(db,args.idea_id,args.status,args.note);print("Feedback saved")
        elif args.cmd=="weekly":
            stats=ingest(db,profile,days=args.days)
            print("Ingest:",json.dumps(stats))
            interest_stats=ingest_interests(db,days=min(365,args.days),per_query=6)
            print("Interest watchlist:",json.dumps(interest_stats))
            if stats["failed_queries"]:print("WARNING: incomplete retrieval; queries failed")
            print("Ideas:",json.dumps(propose(db,profile)))
            text=weekly_report(db,profile)
            out=Path("reports")/("weekly-"+__import__("datetime").date.today().isoformat()+".md")
            out.parent.mkdir(exist_ok=True,parents=True);out.write_text(text,encoding="utf-8")
            print("Report:",out)
            if args.email:
                from email.message import EmailMessage
                import smtplib,ssl
                required=["SMTP_HOST","SMTP_USER","SMTP_PASSWORD","REPORT_TO"]
                if not all(os.getenv(k) for k in required):raise ValueError("SMTP configuration incomplete")
                msg=EmailMessage()
                msg["From"]=os.environ["SMTP_USER"];msg["To"]=os.environ["REPORT_TO"]
                msg["Subject"]="Research Opportunity Brief"
                msg.set_content(text)
                with smtplib.SMTP_SSL(os.environ["SMTP_HOST"],int(os.getenv("SMTP_PORT","465")),context=ssl.create_default_context()) as smtp:
                    smtp.login(os.environ["SMTP_USER"],os.environ["SMTP_PASSWORD"]);smtp.send_message(msg)
                print("Email sent")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
