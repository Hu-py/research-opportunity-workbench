"use client";

import {useCallback,useEffect,useMemo,useState} from "react";
import {BookOpen,CheckCircle2,FileDown,RefreshCw,ShieldAlert,GitMerge,Database} from "lucide-react";
import {api} from "@/lib/api";

type Gate = {status:string;note:string};
type Review = {
  grade:string;verdict:string;novelty:string;note:string;
  gates:Record<string,Gate>;fatal_gaps:string[];risks:string[];
  minimum_data:string[];stop_conditions:string[];
};
type Paper = {id:string;title:string;url:string;doi:string;venue:string};
type Topic = {
  id:string;line_id:string;title:string;question:string;method:string;
  grade:"A"|"B"|"C"|"D";status:string;version:number;
  review:Review;papers:Paper[];related_ai_cards:number;updated_at:string|null;
  history:{version:number;action:string;detail:Record<string,unknown>;created_at:string|null}[];
};
type Report = {period:string;topic_count:number;updated_at:string|null};
type RadarResponse = {topics:Topic[];reports:Report[];latest_markdown:string;note:string};

const GATES:[string,string][]=[
  ["planning_question","规划问题"],
  ["data_access","数据可得"],
  ["construct_validity","构念有效"],
  ["prior_art","文献增量"],
  ["scope","规模可控"],
];
const LEVEL:Record<string,string>={
  A:"A · 人工核验",B:"B · 数据待预检",C:"C · 缺前置条件",D:"D · 暂缓",
};
const LEVEL_COLOR:Record<string,string>={
  A:"#117a50",B:"#5145aa",C:"#a97421",D:"#a33b4b",
};

export default function ResearchRadar({canEdit}:{canEdit:boolean}){
  const [data,setData]=useState<RadarResponse|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [message,setMessage]=useState("");
  const [grade,setGrade]=useState("全部");
  const [expanded,setExpanded]=useState<string|null>(null);
  const [decisions,setDecisions]=useState<Record<string,string>>({});
  const [notes,setNotes]=useState<Record<string,string>>({});
  const load=useCallback(async()=>{
    try{
      const result=await api<RadarResponse>("radar");
      setData(result);setError("");
    }catch(e){setError(e instanceof Error?e.message:"科研雷达加载失败");}
  },[]);
  useEffect(()=>{void load();},[load]);
  const topics=useMemo(()=>(
    data?.topics.filter(x=>grade==="全部"||x.grade===grade)||[]
  ),[data,grade]);
  async function refresh(){
    setBusy(true);setError("");setMessage("");
    try{
      const r=await api<{sync:{new_topics:number;revised_topics:number}}>("radar/refresh",{method:"POST"});
      setMessage("更新完成：新增 "+r.sync.new_topics+" 个选题，更新 "+r.sync.revised_topics+" 个历史选题。");
      await load();
    }catch(e){setError(e instanceof Error?e.message:"更新失败");}
    finally{setBusy(false);}
  }
  async function submitReview(topic:Topic){
    const status=decisions[topic.id]||topic.status;
    const note=notes[topic.id]||"";
    setBusy(true);setError("");setMessage("");
    try {
      await api("radar/topics/"+encodeURIComponent(topic.id),{
        method:"PATCH",
        body:JSON.stringify({status,note}),
      });
      setMessage("已保存研究者反馈，选题版本将持续保留。");
      setNotes(current=>({...current,[topic.id]:""}));
      await load();
    }catch(e){setError(e instanceof Error?e.message:"反馈保存失败");}
    finally{setBusy(false);}
  }
  function download(){
    if(!data?.latest_markdown)return;
    const blob=new Blob([data.latest_markdown],{type:"text/markdown;charset=utf-8"});
    const url=URL.createObjectURL(blob);
    const link=document.createElement("a");link.href=url;
    link.download="科研雷达-"+(data.reports[0]?.period||"latest")+".md";
    link.click();URL.revokeObjectURL(url);
  }
  return <div style={{display:"grid",gap:18}}>
    <div className="page-heading">
      <div className="mini-label">RESEARCH RADAR · EVIDENCE FIRST</div>
      <h1>科研雷达与选题评审</h1>
      <p>论文证据 → 跨领域切口 → 五道可行性门槛 → 滚动去重与历史积累。自动分级仅供预筛，不代表创新性已通过核验。</p>
    </div>
    <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",gap:12,flexWrap:"wrap"}}>
      <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
        {["全部","A","B","C","D"].map(x=><button type="button" className={"filter-pill "+(grade===x?"filter-active":"")}
          key={x} onClick={()=>setGrade(x)}>{x==="全部"?"全部选题":LEVEL[x]}</button>)}
      </div>
      <div style={{display:"flex",gap:8}}>
        <button type="button" className="btn" onClick={download} disabled={!data?.latest_markdown}>
          <FileDown size={15}/> 导出本期周报
        </button>
        {canEdit&&<button type="button" className="btn" disabled={busy} onClick={()=>void refresh()}>
          <RefreshCw size={15}/> {busy?"正在整理…":"整理已有 AI 结果"}
        </button>}
      </div>
    </div>
    {error&&<div className="warning-note" role="alert">{error}</div>}
    {message&&<p style={{color:"#13754b"}}><CheckCircle2 size={15} style={{display:"inline",verticalAlign:"middle"}}/> {message}</p>}
    <div className="warning-note">
      <ShieldAlert size={17} style={{display:"inline",verticalAlign:"middle",marginRight:7}}/>
      数据登记不等于实际可用；仅有摘要不能判定全文缺陷；缺少定向先前研究检索时，所有创新性判断都保持“未核验”。
    </div>
    <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(180px,1fr))",gap:12}}>
      <div className="idea-card"><span className="mini-label">TOPICS</span><h2>{data?.topics.length||0}</h2><p className="small muted">累计候选选题</p></div>
      <div className="idea-card"><span className="mini-label">B · PREFLIGHT</span><h2>{data?.topics.filter(t=>t.grade==="B").length||0}</h2><p className="small muted">可优先数据预检</p></div>
      <div className="idea-card"><span className="mini-label">HISTORY</span><h2>{data?.topics.reduce((n,t)=>n+t.version-1,0)||0}</h2><p className="small muted">累积版本更新</p></div>
      <div className="idea-card"><span className="mini-label">REPORTS</span><h2>{data?.reports.length||0}</h2><p className="small muted">数据库归档周报</p></div>
    </div>
    {topics.length===0?<div className="empty"><Database size={28}/><h3>暂无研究雷达选题</h3>
      <p>先在「AI 选题实验台」运行并完成论文分析，再通过“整理已有 AI 结果”导入滚动选题池。不会凭空生成论文或选题。</p></div>:
      topics.map(t=><article key={t.id} className="idea-card">
        <div className="idea-heading" style={{gap:14,alignItems:"start"}}>
          <div>
            <span className="mini-label">RADAR · {t.line_id} · V{t.version}</span>
            <h3>{t.title}</h3>
            <p>{t.question}</p>
          </div>
          <span style={{fontWeight:700,color:LEVEL_COLOR[t.grade],whiteSpace:"nowrap"}}>{LEVEL[t.grade]}</span>
        </div>
        <div className="idea-tags">
          <span className="method-chip">{t.method||"跨领域方法待明确"}</span>
          <span className="method-chip">{t.papers.length} 篇来源论文</span>
          <span className="method-chip">{t.related_ai_cards} 次 AI 证据记录</span>
        </div>
        <button type="button" className="btn" onClick={()=>setExpanded(expanded===t.id?null:t.id)}>
          {expanded===t.id?"收起审核详情":"展开五道门槛与证据"}
        </button>
        {expanded===t.id&&<div style={{paddingTop:16,display:"grid",gap:12}}>
          <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(240px,1fr))",gap:9}}>
            {GATES.map(([key,label])=><div key={key} style={{border:"1px solid #e6e8ef",borderRadius:12,padding:13}}>
              <strong>{label} · {t.review?.gates?.[key]?.status||"待审核"}</strong>
              <p className="small muted">{t.review?.gates?.[key]?.note||"尚无可验证信息"}</p>
            </div>)}
          </div>
          {t.review?.fatal_gaps?.length>0&&<p><strong>关键风险：</strong>{t.review.fatal_gaps.join("；")}</p>}
          {t.review?.minimum_data?.length>0&&<p><strong>最低数据：</strong>{t.review.minimum_data.join("；")}</p>}
          {t.review?.stop_conditions?.length>0&&<p><strong>停止条件：</strong>{t.review.stop_conditions.join("；")}</p>}
          <h4><BookOpen size={16} style={{display:"inline"}}/> 证据论文</h4>
          {t.papers.map(p=><p key={p.id} className="small">
            <a href={p.url} target="_blank" rel="noopener noreferrer">{p.title}</a>
            {p.venue?" · "+p.venue:""}
          </p>)}
          <p className="small muted"><GitMerge size={15} style={{display:"inline"}}/> 相似选题采用保守文本合并策略；复杂同义关系仍需人工审核。</p>
          <h4>选题演化记录</h4>
          {(t.history||[]).map(e=><p key={e.version} className="small muted">
            V{e.version} · {e.action} · {e.created_at?.slice(0,16)||""}
            {typeof e.detail.note==="string"&&e.detail.note?" · "+e.detail.note:""}
          </p>)}
          {canEdit&&<div style={{display:"grid",gap:8,borderTop:"1px solid #e8ebf1",paddingTop:14}}>
            <strong>研究者人工审核</strong>
            <select value={decisions[t.id]||t.status} onChange={e=>setDecisions(v=>({...v,[t.id]:e.target.value}))}
              aria-label="更新选题状态" style={{padding:10,borderRadius:10,border:"1px solid #dce2eb"}}>
              {[
                ["candidate","待评估"],["watch","持续关注"],["shortlist","重点选题"],
                ["experiment","准备实验"],["rejected","暂不考虑"],["archived","归档"],
              ].map(([value,label])=><option key={value} value={value}>{label}</option>)}
            </select>
            <textarea aria-label="研究者审核备注" placeholder="判断依据、需要补充的数据或决定停止的条件"
              rows={2} value={notes[t.id]||""} maxLength={1500}
              onChange={e=>setNotes(v=>({...v,[t.id]:e.target.value}))}
              style={{padding:10,borderRadius:10,border:"1px solid #dce2eb",resize:"vertical"}}/>
            <button type="button" className="btn" disabled={busy}
              onClick={()=>void submitReview(t)}>{busy?"保存中…":"保存审核与新版本"}</button>
          </div>}
        </div>}
      </article>)}
    {!!data?.reports.length&&<section className="idea-card">
      <h3>最新一次科研雷达简报 · {data.reports[0].period}</h3>
      <p className="small muted">报告已保存于后端数据库。前端实时读取，不必重新部署。</p>
      <details><summary>查看 Markdown 原文</summary>
        <pre style={{whiteSpace:"pre-wrap",fontSize:12,maxHeight:400,overflow:"auto"}}>{data.latest_markdown}</pre>
      </details>
    </section>}
  </div>;
}
