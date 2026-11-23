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
from backend.task_source_scopes import task_source_context
from backend.interests import ingest_interests
from backend.radar_pipeline import sync_ai_opportunities, generate_weekly

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
            source_context=task_source_context(db,task_id)
            if source_context:
                log("source_scope",
                    "本次任务已锁定专属期刊清单 V" + str(source_context["scope_version"]) +
                    "，A/B/C 共 " + str(sum(len(v) for v in source_context["groups"].values())) +
                    " 个来源。")
            if task.kind=="explore":
                result=ResearchAgent(
                    db,log=log,openalex_client=client,model_client=model_client,
                    source_context=source_context,
                ).run(task.query)
                if source_context:
                    result["source_scope"]={
                        "groups":source_context["groups"],
                        "version":source_context["scope_version"],
                        "enforced":True,
                    }
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
                if source_context:
                    collected=ingest(db,profile,days=14,limit=10,client=client,
                                     source_ids_by_mode={
                                         "direct":source_context["direct_ids"],
                                         "method":source_context["method_ids"],
                                     })
                    # Do not mix unrelated interest topics or global historical
                    # Radar cards into a strict SC01 report.
                    report=weekly_report(
                        db,profile,allowed_venues=source_context["allowed_venues"],
                        include_team_ideas=False,include_interests=False,
                    )
                    report=("> 本期采用任务专属来源 V"+
                            str(source_context["scope_version"])+
                            "：A 应用场景 / B 前沿视角 / C 技术方法。\n\n"+report)
                    result={"mode":"weekly_scoped","answer":report,"papers":collected,
                            "source_scope":{"groups":source_context["groups"],
                                            "version":source_context["scope_version"],
                                            "enforced":True}}
                    log("source_review","已排除非本任务来源的兴趣分支和全局 Radar 结果")
                else:
                    collected=ingest(db,profile,days=14,limit=10,client=client)
                    interest_stats=ingest_interests(db,days=14,per_query=6,client=client)
                    log("interests","已检索手动兴趣分支，并保留独立来源标签")
                    ideas=propose(db,profile)
                    log("radar","正在合并 AI 选题并进行五道可行性预审")
                    radar_stats=sync_ai_opportunities(db)
                    radar_report=generate_weekly(db)
                    result={"mode":"weekly","answer":weekly_report(db,profile)+"\n\n"+radar_report,
                            "radar":radar_stats,
                            "papers":collected,"interest_papers":interest_stats,"ideas":ideas}
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
