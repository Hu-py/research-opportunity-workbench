"""CLI entrypoints for LLM-led scheduled research discovery and weekly synthesis."""
import argparse
import json
import os
from pathlib import Path
from datetime import date

from .core import session_factory, set_profile, get_profile, feedback
from backend.discovery import create_run
from backend.discovery_runner import execute_discovery
from backend.ai_lab import create_scheduled_run, execute as execute_ai_analysis
from backend.llm_relations import execute_llm_relations
from backend.llm_weekly import generate_weekly_brief
from backend.model_vault import ModelCredential, load_key


def _llm_ready(db):
    credential=db.get(ModelCredential,"deepseek")
    if not credential or not credential.encrypted_key:
        return False,"DeepSeek API Key 未配置"
    try:
        return bool(load_key(db)),""
    except ValueError as exc:
        return False,str(exc)


def _run_discovery(factory, profile):
    with factory() as db:
        run=create_run(db,profile,source="scheduled")
        if not run:
            return {"status":"skipped","reason":"没有启用的研究主线或手动兴趣分支"}
        ident=run.id
    execute_discovery(factory,ident)
    with factory() as db:
        from backend.discovery import runs
        return next((x for x in runs(db) if x["id"]==ident),{"id":ident,"status":"unknown"})


def _run_optional_ai(factory):
    with factory() as db:
        run=create_scheduled_run(db)
        ident=run.id if run else None
    if not ident:
        return {"status":"skipped","reason":"未开启每日 AI 分析、没有已审核论文或已有任务"}
    ok=execute_ai_analysis(factory,ident)
    return {"id":ident,"status":"completed" if ok else "failed"}


def main(argv=None):
    parser=argparse.ArgumentParser(prog="research-wb")
    sub=parser.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("profile-import")
    p.add_argument("path")
    # Keep legacy command names so old scripts fail with a clear migration message.
    sub.add_parser("ingest",help="deprecated: use daily/weekly LLM discovery")
    sub.add_parser("ideate",help="deprecated: use the LLM AI Lab")
    p=sub.add_parser("feedback")
    p.add_argument("idea_id");p.add_argument("status");p.add_argument("--note",default="")
    sub.add_parser("daily")
    p=sub.add_parser("weekly")
    p.add_argument("--days",type=int,default=7)
    p.add_argument("--email",action="store_true")
    p.add_argument("--ai",action="store_true",help="also run the configured AI Lab scheduled analysis")
    args=parser.parse_args(argv)
    if os.getenv("GITHUB_ACTIONS")=="true" and not os.getenv("DATABASE_URL"):
        parser.error("GitHub Actions requires a persistent DATABASE_URL")
    if args.cmd in ("ingest","ideate"):
        parser.error("该规则式命令已停用。请使用 daily/weekly 的 LLM 驱动科研发现流程。")
    factory=session_factory()
    with factory() as db:
        if args.cmd=="profile-import":
            set_profile(db,json.loads(Path(args.path).read_text(encoding="utf-8")))
            print("Research profile saved in database")
            return 0
        profile=get_profile(db)
        if not profile:
            parser.error("No research profile: establish the team research portrait first")
        ready,reason=_llm_ready(db)
    if not ready:
        if args.cmd=="weekly":
            raise RuntimeError("Weekly LLM workflow requires a configured model key: "+reason)
        print("LLM workflow skipped:",reason)
        return 0

    if args.cmd=="feedback":
        with factory() as db:
            feedback(db,args.idea_id,args.status,args.note)
        print("Feedback saved")
        return 0

    if args.cmd=="daily":
        discovery=_run_discovery(factory,profile)
        print("LLM discovery:",json.dumps(discovery,ensure_ascii=False))
        ai=_run_optional_ai(factory)
        print("AI opportunity analysis:",json.dumps(ai,ensure_ascii=False))
        return 0

    if args.cmd=="weekly":
        discovery=_run_discovery(factory,profile)
        print("LLM discovery:",json.dumps(discovery,ensure_ascii=False))
        relations=execute_llm_relations(factory)
        print("LLM data relations:",json.dumps(relations,ensure_ascii=False))
        if args.ai:
            ai=_run_optional_ai(factory)
            print("AI opportunity analysis:",json.dumps(ai,ensure_ascii=False))
        report=generate_weekly_brief(factory,days=args.days)
        if report.get("status")!="completed":
            raise RuntimeError(report.get("reason","LLM weekly report failed"))
        text=report["markdown"]
        out=Path("reports")/("weekly-"+date.today().isoformat()+".md")
        out.parent.mkdir(exist_ok=True,parents=True)
        out.write_text(text,encoding="utf-8")
        print("LLM weekly report:",out)
        if args.email:
            from email.message import EmailMessage
            import smtplib,ssl
            required=["SMTP_HOST","SMTP_USER","SMTP_PASSWORD","REPORT_TO"]
            if not all(os.getenv(k) for k in required):
                raise ValueError("SMTP configuration incomplete")
            msg=EmailMessage()
            msg["From"]=os.environ["SMTP_USER"];msg["To"]=os.environ["REPORT_TO"]
            msg["Subject"]="Research Opportunity Brief"
            msg.set_content(text)
            with smtplib.SMTP_SSL(os.environ["SMTP_HOST"],int(os.getenv("SMTP_PORT","465")),
                                  context=ssl.create_default_context()) as smtp:
                smtp.login(os.environ["SMTP_USER"],os.environ["SMTP_PASSWORD"])
                smtp.send_message(msg)
            print("Email sent")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
