"use client";

import {useState} from "react";
import {ArrowRight, ArrowUpRight, BookOpen, ChevronDown, ChevronUp, FileText, Loader2, Send, ShieldCheck, Workflow} from "lucide-react";
import type {Task} from "@/lib/types";

type Props={
  task:Task|null;
  question:string;
  onQuestionChange:(value:string)=>void;
  onSubmit:()=>void;
  onOpenLegacy:()=>void;
  busy:boolean;
  canEdit:boolean;
  onRetry:(task:Task)=>void;
};

function allowedUrl(url:string){
  try{
    const parsed=new URL(url);
    return parsed.protocol==="https:"||parsed.protocol==="http:" ? parsed.href:null;
  }catch{return null;}
}
function statusLabel(status:Task["status"]){
  return ({queued:"排队中",running:"执行中",completed:"已完成",failed:"执行失败"} as const)[status];
}

export default function AtlasConversation({task,question,onQuestionChange,onSubmit,onOpenLegacy,busy,canEdit,onRetry}:Props){
  const [showEvidence,setShowEvidence]=useState(false);
  const [showTrace,setShowTrace]=useState(false);
  const isPending=task?.status==="queued"||task?.status==="running";
  const canSend=canEdit&&!busy&&question.trim().length>=6&&question.length<=2000;
  return <div className="atlas-chat-view">
    <div className="atlas-chat-head">
      <div>
        <div className="atlas-kicker">RESEARCH AGENT / TASK MODE</div>
        <h1>科研对话</h1>
      </div>
      <div className="atlas-chat-status"><ShieldCheck size={14}/> 单次研究任务 · 不代表持久化聊天</div>
    </div>

    <div className="atlas-chat-thread" aria-live="polite">
      {!task ? <div className="atlas-chat-start">
        <span className="atlas-chat-start-mark">RA</span>
        <h2>开始一项科研探索</h2>
        <p>提出具体研究问题，系统将通过现有 Research Agent 创建一条真实任务，并提供执行状态及论文证据。</p>
        <div className="atlas-chat-suggestions">
          {["城市健康预测中有哪些可迁移的图学习方法？","如何梳理近期城市科学中的新测度研究？","如何检索与跨地区外推相关的研究证据？"].map(prompt=>
            <button type="button" key={prompt} onClick={()=>onQuestionChange(prompt)}>{prompt}<ArrowRight size={14}/></button>)}
        </div>
      </div> : <div className="atlas-chat-messages">
        <div className="atlas-message atlas-message-user">
          <div className="atlas-avatar atlas-avatar-user">我</div>
          <div className="atlas-message-content">
            <span className="atlas-message-by">研究问题</span>
            <div className="atlas-message-text">{task.query||"未记录原始问题"}</div>
          </div>
        </div>
        <div className="atlas-message atlas-message-agent">
          <div className="atlas-avatar">RA</div>
          <div className="atlas-message-content">
            <div className="atlas-message-title"><strong>Research Agent</strong><span className={"atlas-run-state atlas-run-"+task.status}>{statusLabel(task.status)}</span></div>
            {task.error&&<div className="atlas-run-error" role="alert">{task.error}</div>}
            {task.result.answer ? <div className="atlas-message-answer">{task.result.answer}</div>:
              <p className="atlas-muted">{task.status==="failed"?"本次任务未生成科研回答。":isPending?"后台正在处理本次研究任务；执行结果将出现在这里。":"本次任务没有可显示的回答。"}</p>}
            {task.result.mode&&<p className="atlas-mode">实际运行模式：{task.result.mode}</p>}
            <div className="atlas-chat-result-actions">
              <button type="button" onClick={()=>setShowEvidence(x=>!x)} aria-expanded={showEvidence}>
                <BookOpen size={15}/> 论文证据（{task.result.sources?.length||0}） {showEvidence?<ChevronUp size={14}/>:<ChevronDown size={14}/>}
              </button>
              <button type="button" onClick={()=>setShowTrace(x=>!x)} aria-expanded={showTrace}>
                <Workflow size={15}/> 执行记录（{task.events.length}） {showTrace?<ChevronUp size={14}/>:<ChevronDown size={14}/>}
              </button>
              <button type="button" onClick={onOpenLegacy}><FileText size={15}/> 任务详情 <ArrowRight size={14}/></button>
            </div>
            {showEvidence&&<div className="atlas-evidence-content">
              {!task.result.sources?.length?<p className="atlas-muted">没有可供核查的论文来源，不能将本次输出视为已验证的科研证据。</p>:
                task.result.sources.map((paper,i)=><div className="atlas-evidence-item" key={paper.id||i}>
                  <div><strong>{paper.title}</strong><small>{paper.venue||"来源待核验"} · {paper.published||"日期待核验"}</small></div>
                  {paper.url&&allowedUrl(paper.url)&&<a href={allowedUrl(paper.url)!} target="_blank" rel="noopener noreferrer" aria-label={"查看论文："+paper.title}><ArrowUpRight size={17}/></a>}
                </div>)}
            </div>}
            {showTrace&&<div className="atlas-trace-content">
              {!task.events.length?<p className="atlas-muted">任务尚无执行步骤记录。</p>:
                task.events.map((event,i)=><div className="atlas-trace-item" key={i}>
                  <span className="atlas-trace-dot"/><div><strong>{event.step}</strong><p>{event.detail}</p><small>{event.at}</small></div>
                </div>)}
            </div>}
            {task.status==="queued"&&canEdit&&<button type="button" className="atlas-secondary-button" disabled={busy} onClick={()=>onRetry(task)}>重新调度排队任务</button>}
          </div>
        </div>
      </div>}
    </div>
    <div className="atlas-chat-compose-area">
      <div className="atlas-composer">
        <label htmlFor="atlas-research-question" className="atlas-sr-only">输入科研问题</label>
        <textarea id="atlas-research-question" value={question} onChange={e=>onQuestionChange(e.target.value)}
          onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();if(canSend)onSubmit();}}}
          maxLength={2000} rows={3} disabled={!canEdit} placeholder={canEdit?"输入研究问题，按 Enter 发送；Shift + Enter 换行":"当前角色无权提交科研任务"}/>
        <div className="atlas-compose-bottom">
          <span>{question.length}/2000 · 每次发送创建一项独立科研任务</span>
          <button type="button" aria-label="提交科研任务" disabled={!canSend} onClick={onSubmit}>
            {busy?<Loader2 size={17} className="spin"/>:<Send size={17}/>}<span>发送</span>
          </button>
        </div>
      </div>
      <p className="atlas-chat-disclaimer">当前已连接真实任务及执行结果。多轮上下文、私人会话和团队共同聊天需后端权限与持久化支持，尚未作为已实现功能提供。</p>
    </div>
  </div>;
}
