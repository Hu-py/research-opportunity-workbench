"""Worker process; separate it from the API service in production."""
from __future__ import annotations

import argparse
import json
import os
import time
from sqlalchemy import select
from research_workbench.core import session_factory, get_profile, ingest, propose, weekly_report
from backend.tasks import ResearchTask, claim, next_queued, event, utc_now
from backend.agent import ResearchAgent

def run_task(factory, task_id: str, already_claimed=False, client=None, model_client=None):
    with factory() as db:
        if not already_claimed and not claim(db,task_id):
            return False
        task=db.get(ResearchTask,task_id)
        if task is None: return False
        def log(step,msg): event(db,task,step,msg)
        try:
            log("start","科研任务已启动："+task.kind)
            profile=get_profile(db)
            if task.kind=="explore":
                result=ResearchAgent(db,log=log,openalex_client=client,model_client=model_client).run(task.query)
            elif not profile:
                raise ValueError("请先保存研究者画像，才能执行文献更新或周报。")
            elif task.kind=="sync":
                log("search","正在采集并归一化新论文")
                collected=ingest(db,profile,days=14,limit=10,client=client)
                log("ideas","正在更新选题证据与版本")
                ideas=propose(db,profile)
                result={"mode":"pipeline","papers":collected,"ideas":ideas,
                        "answer":f"新增论文 {collected['new_papers']} 篇，新选题 {ideas['new_ideas']} 个，已更新选题 {ideas['revised_ideas']} 个。"}
            elif task.kind=="weekly":
                log("search","正在收集周报相关文献")
                collected=ingest(db,profile,days=14,limit=10,client=client)
                ideas=propose(db,profile)
                result={"mode":"weekly","answer":weekly_report(db,profile),
                        "papers":collected,"ideas":ideas}
            else:
                raise ValueError("Unsupported task")
            task.result_json=json.dumps(result,ensure_ascii=False)
            task.status="completed"
            task.updated_at=utc_now()
            db.commit()
            log("done","科研任务成功完成")
        except Exception as exc:
            db.rollback()
            task=db.get(ResearchTask,task_id)
            task.status="failed"
            task.error=str(exc)[:350]
            task.updated_at=utc_now()
            db.commit()
            log("failed","任务失败；可查看错误信息后重新提交。")
        return True

def execute_once(factory):
    with factory() as db:
        selected=next_queued(db)
    if not selected:return False
    run_task(factory,selected,already_claimed=True)
    return True

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--once",action="store_true")
    parser.add_argument("--interval",type=int,default=4)
    args=parser.parse_args(argv)
    factory=session_factory()
    if args.once:
        execute_once(factory)
        return
    while True:
        try:
            if not execute_once(factory):time.sleep(max(1,args.interval))
        except KeyboardInterrupt:break
        except Exception as exc:
            print("Worker error:",str(exc)[:250],flush=True)
            time.sleep(max(1,args.interval))

if __name__=="__main__":
    main()
