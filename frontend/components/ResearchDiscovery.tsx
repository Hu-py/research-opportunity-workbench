"use client";

import {useCallback,useEffect,useMemo,useState} from "react";
import {BookOpenCheck,Database,RefreshCw,Search,ShieldCheck,Link2,Lightbulb,CheckCircle2,XCircle} from "lucide-react";
import {api} from "@/lib/api";

type Relation={id:string;line_id:string;line_name:string;kind:"dataset"|"achievement";
 label:string;score:number;reason:string;status:"suggested"|"confirmed"|"rejected"};
type Strategy={line_id:string;line_name:string;direct_queries:string[];method_queries:string[];
 enabled:boolean;lookback_days:number;per_query:number;min_score:number;configured:boolean};
type Candidate={id:string;line_id:string;title:string;abstract:string;url:string;doi:string;
 published:string;venue:string;score:number;score_reason:string;matched_queries:string[];
 match_type:string;status:"pending"|"relevant"|"method"|"rejected";review_note:string};
type Run={id:string;status:string;source:string;queries:number;scanned:number;
 new_candidates:number;updated_candidates:number;errors:string[];started_at:string};
type Dashboard={profile_ready:boolean;openalex_key_configured:boolean;
 strategies:Strategy[];relations:Relation[];candidates:Candidate[];runs:Run[];note:string};

export default function ResearchDiscovery({canAdmin,canEdit,onManageSources}:{canAdmin:boolean;canEdit:boolean;onManageSources:()=>void}){
 const [data,setData]=useState<Dashboard|null>(null);
 const [active,setActive]=useState<"links"|"search"|"candidates">("search");
 const [line,setLine]=useState("all");
 const [candidateFilter,setCandidateFilter]=useState("pending");
 const [editor,setEditor]=useState<string|null>(null);
 const [draft,setDraft]=useState<Strategy|null>(null);
 const [directText,setDirectText]=useState("");
 const [methodText,setMethodText]=useState("");
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [notice,setNotice]=useState("");
 const load=useCallback(async()=>setData(await api<Dashboard>("opportunity-engine")),[]);
 useEffect(()=>{void load().catch(e=>setError(String(e)));},[load]);
 const running=data?.runs.some(x=>x.status==="queued"||x.status==="running")||false;
 useEffect(()=>{
   if(!running)return;
   const timer=setInterval(()=>{void load().catch(()=>{});},5500);
   return()=>clearInterval(timer);
 },[running,load]);

 const strategies=data?.strategies||[];
 const selected=useMemo(()=>data?.candidates.filter(x=>
   (line==="all"||x.line_id===line)&&
   (candidateFilter==="all"||x.status===candidateFilter||
    (candidateFilter==="priority"&&x.status==="pending"&&
     x.score>=(data?.strategies.find(s=>s.line_id===x.line_id)?.min_score??60))))||[],
   [data,line,candidateFilter]);
 const relations=useMemo(()=>data?.relations.filter(x=>line==="all"||x.line_id===line)||[],
   [data,line]);
 const latest=data?.runs[0];
 function openEditor(s:Strategy){
   setEditor(s.line_id);setDraft({...s});
   setDirectText(s.direct_queries.join("\n"));setMethodText(s.method_queries.join("\n"));
 }
 async function saveStrategy(){
   if(!draft||!editor)return;
   setBusy(true);setError("");setNotice("");
   try{
     const direct_queries=directText.split(/\n/).map(x=>x.trim()).filter(Boolean);
     const method_queries=methodText.split(/\n/).map(x=>x.trim()).filter(Boolean);
     await api("opportunity-engine/strategies/"+encodeURIComponent(editor),{
       method:"PUT",body:JSON.stringify({...draft,direct_queries,method_queries})});
     setEditor(null);setDraft(null);await load();
     setNotice("检索策略已保存。定时模式只运行管理员主动开启的研究主线。");
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function runSearch(id:string){
   setBusy(true);setError("");setNotice("");
   try{
     const response=await api<{id:string}>("opportunity-engine/run",{
       method:"POST",body:JSON.stringify({line_id:id})});
     setNotice("已启动这条研究主线的文献试抓取："+response.id.slice(0,8)+
       "。候选论文不会自动进入正式文献库。");
     setActive("candidates");setCandidateFilter("pending");await load();
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function reviewRelation(row:Relation,status:Relation["status"]){
   setBusy(true);setError("");
   try{
     await api("opportunity-engine/relations/"+row.id,{method:"PATCH",body:JSON.stringify({status})});
     await load();setNotice(status==="confirmed"?"已确认关联；Agent 可作为可追溯的团队背景使用。":"关联状态已更新。");
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 async function reviewPaper(row:Candidate,status:Candidate["status"]){
   setBusy(true);setError("");
   try{
     await api("opportunity-engine/candidates/"+row.id,{
       method:"PATCH",body:JSON.stringify({status,note:""})});
     await load();
     setNotice(status==="relevant"?"已批准，论文进入正式论文情报库。":
       status==="method"?"已标注为方法借鉴，论文进入正式论文情报库。":"候选论文已排除。");
   }catch(e){setError(e instanceof Error?e.message:String(e));}
   finally{setBusy(false);}
 }
 return <div className="discovery-page repository-root">
   <div className="page-heading">
     <span className="panel-kicker">RESEARCH OPPORTUNITY ENGINE · P0 + P1</span>
     <h1>科研关联与文献发现</h1>
     <p>已有成果、数据目录与研究方向之间建立可核验关系，再按研究问题和方法分别检索新论文。</p>
     <div className="inline-actions">
       <button className="btn btn-secondary" onClick={onManageSources}><BookOpenCheck size={14}/>管理学术来源</button>
       <span className="small muted">仅使用 Academic Source Registry 中已启用且已核验的 OpenAlex 来源，不回退到全库宽泛检索。</span>
     </div>
   </div>
   <div className="repository-stat-row">
     <div><strong>{data?.relations.filter(x=>x.status==="confirmed").length??"…"}</strong><span>已确认知识关联</span></div>
     <div><strong>{data?.relations.filter(x=>x.status==="suggested").length??"…"}</strong><span>待核对关联</span></div>
     <div><strong>{data?.candidates.filter(x=>x.status==="pending").length??"…"}</strong><span>待审核候选论文</span></div>
     <div><strong>{data?.strategies.filter(x=>x.enabled).length??"…"}</strong><span>每日监测方向</span></div>
   </div>
   {error&&<div className="alert alert-error">{error}</div>}
   {notice&&<div className="alert alert-success">{notice}</div>}
   {data&&!data.openalex_key_configured&&<div className="panel discovery-key-hint">
     <strong>OpenAlex 免费 API Key 尚未配置</strong>
     <p className="small muted">少量匿名试用可能成功，但用完额度后会报 HTTP 409。请在 <a href="https://openalex.org/settings/api" target="_blank" rel="noopener noreferrer">OpenAlex</a> 获取免费 Key，在 Render → Environment 添加 <code>OPENALEX_API_KEY</code>。只需填写在服务器，不要发到聊天或上传 GitHub。</p>
   </div>}
   {latest&&<div className="panel discovery-run-status">
     <div className="discovery-run-header"><strong>最近一次文献检索：{latest.status==="completed"?"完成":latest.status==="running"?"运行中":latest.status==="queued"?"排队中":latest.status==="partial"?"部分成功":"失败"}</strong>
       <span>{latest.started_at?.slice(0,19).replace("T"," ")||""} UTC</span></div>
     <p className="small muted">已执行 {latest.queries} 个检索请求 · 扫描 {latest.scanned} 条 · 新增候选 {latest.new_candidates} 篇 · 重复匹配 {latest.updated_candidates} 条</p>
     {latest.errors.length>0&&<div className="discovery-run-errors">
       <strong>失败原因与排查建议</strong>
       {latest.errors.slice(0,4).map((e,i)=><p key={i}>{e}</p>)}
     </div>}
     {latest.status==="failed"&&latest.errors.length===0&&<p className="small muted">已记录失败，但旧版本未写入详细错误原因；可检查配置后重新试抓取以获得新诊断。</p>}
   </div>}
   {!data?.profile_ready&&<div className="panel"><h3>请先建立团队研究画像</h3><p className="small muted">至少保存一条研究主线及其检索词。CUSP 数据登记和团队历史成果不会被自动覆盖。</p></div>}
   <section className="panel">
     <div className="discovery-toolbar">
       <div className="filter-pills">
         <button className={"filter-pill "+(active==="links"?"active":"")} onClick={()=>setActive("links")}><Link2 size={14}/> 研究关联</button>
         <button className={"filter-pill "+(active==="search"?"active":"")} onClick={()=>setActive("search")}><Search size={14}/> 检索策略</button>
         <button className={"filter-pill "+(active==="candidates"?"active":"")} onClick={()=>setActive("candidates")}><BookOpenCheck size={14}/> 候选论文</button>
       </div>
       <div className="inline-actions">
         <select aria-label="研究主线" value={line} onChange={e=>setLine(e.target.value)}>
           <option value="all">所有研究主线</option>
           {strategies.map(x=><option key={x.line_id} value={x.line_id}>{x.line_name}</option>)}
         </select>
         <button className="btn btn-secondary" disabled={busy} onClick={()=>void load()}><RefreshCw size={14}/> 刷新</button>
       </div>
     </div>
     {active==="links"&&<>
       <p className="small muted">以下根据团队研究问题与 CUSP 数据属性、已核验成果主题推断，仅是候选关联。管理员确认后会保留审核状态与操作记录，不等于实际数据可用或已经验证方法。</p>
       <div className="discovery-record-list">
         {relations.length===0?<div className="empty"><Database size={26}/><p>未发现可匹配关联。请检查团队研究画像中的问题与关键词。</p></div>:
         relations.map(x=><article className="discovery-record" key={x.id}>
           <div className="discovery-labels"><span>{x.line_name}</span><span>{x.kind==="dataset"?"CUSP 数据":"团队已有成果"}</span>
             <span className={x.status==="confirmed"?"disc-confirmed":""}>{x.status==="confirmed"?"已确认":x.status==="rejected"?"已排除":"建议关联"}</span></div>
           <h3>{x.label}</h3><p className="small muted">{x.reason}</p>
           <div className="discovery-actions"><small>主题匹配参考分：{Math.round(x.score)}/100</small>
             {canAdmin&&<div className="inline-actions">
               <button disabled={busy} className="btn btn-secondary" onClick={()=>void reviewRelation(x,"confirmed")}><CheckCircle2 size={14}/> 确认</button>
               <button disabled={busy} className="btn btn-secondary" onClick={()=>void reviewRelation(x,"rejected")}><XCircle size={14}/> 排除</button>
             </div>}
           </div>
         </article>)}
       </div>
     </>}
     {active==="search"&&<>
       <p className="small muted">每条研究主线有“研究问题”和“方法迁移”两个检索通道。定时抓取默认关闭，只有管理员主动开启的方向才会由现有每日任务触发；不消耗模型 API。</p>
       <div className="discovery-record-list">
         {strategies.filter(x=>line==="all"||line===x.line_id).map(x=><article className="discovery-record" key={x.line_id}>
           <div className="discovery-labels"><span>{x.enabled?"每日监测已开启":"定时监测关闭"}</span><span>近 {x.lookback_days} 天</span><span>每词最多 {x.per_query} 篇</span></div>
           <h3>{x.line_name}</h3>
           {editor===x.line_id&&draft?<div className="discovery-editor">
             <label>直接相关检索（每行一个，最多 3 条）<textarea rows={4} value={directText} onChange={e=>setDirectText(e.target.value)}/></label>
             <label>方法迁移检索（每行一个，最多 3 条）<textarea rows={4} value={methodText} onChange={e=>setMethodText(e.target.value)}/></label>
             <div className="discovery-options">
               <label><input type="checkbox" checked={draft.enabled} onChange={e=>setDraft({...draft,enabled:e.target.checked})}/> 开启每天自动抓取</label>
               <label>回溯天数<input type="number" min={7} max={180} value={draft.lookback_days} onChange={e=>setDraft({...draft,lookback_days:Number(e.target.value)})}/></label>
               <label>每词最多<input type="number" min={1} max={12} value={draft.per_query} onChange={e=>setDraft({...draft,per_query:Number(e.target.value)})}/></label>
               <label>重点推荐分<input type="number" min={0} max={100} value={draft.min_score} onChange={e=>setDraft({...draft,min_score:Number(e.target.value)})}/></label>
             </div>
             <div className="inline-actions">
               <button className="btn btn-primary" disabled={busy} onClick={()=>void saveStrategy()}>保存策略</button>
               <button className="btn btn-secondary" onClick={()=>setEditor(null)}>取消</button>
             </div>
           </div>:<div className="discovery-channels">
             <p><b>问题检索：</b>{x.direct_queries.join(" · ")||"尚未配置"}</p>
             <p><b>方法检索：</b>{x.method_queries.join(" · ")||"尚未配置"}</p>
           </div>}
           <div className="discovery-actions"><small>推荐阈值：{x.min_score}/100 · 每轮最多 4 个检索请求</small>
             <div className="inline-actions">
               {canAdmin&&<button className="btn btn-secondary" disabled={busy} onClick={()=>openEditor(x)}>编辑策略</button>}
               {canEdit&&<button className="btn btn-primary" disabled={busy} onClick={()=>void runSearch(x.line_id)}><Search size={14}/> 试抓取</button>}
             </div>
           </div>
         </article>)}
       </div>

     </>}
     {active==="candidates"&&<>
       <div className="discovery-inbox-top"><p className="small muted">候选论文先进入待审核池；只有人工标注“相关”或“方法借鉴”后才写入正式论文情报库。</p>
         <select aria-label="候选论文状态" value={candidateFilter} onChange={e=>setCandidateFilter(e.target.value)}>
           <option value="pending">待审核</option><option value="priority">重点候选（达到主线阈值）</option><option value="relevant">已确认为相关</option>
           <option value="method">方法借鉴</option><option value="rejected">已排除</option><option value="all">全部</option>
         </select></div>
       <div className="discovery-record-list">
         {!selected.length?<div className="empty"><BookOpenCheck size={26}/><h3>当前没有候选论文</h3><p>先在“检索策略”中试抓取一条研究主线。</p></div>:
         selected.map(x=><article className="discovery-record" key={x.id}>
           <div className="discovery-labels"><span>{strategies.find(s=>s.line_id===x.line_id)?.line_name||x.line_id}</span>
             <span>{x.match_type==="method"?"方法迁移":"研究问题"}</span>
             <span className={x.score>=(strategies.find(s=>s.line_id===x.line_id)?.min_score??60)?"disc-confirmed":""}>检索相关度 {x.score}/100</span></div>
           <h3>{x.url?<a href={x.url} target="_blank" rel="noopener noreferrer">{x.title}</a>:x.title}</h3>
           <p className="small muted">{x.venue||"期刊待核实"} · {x.published||"发表时间未知"} · DOI：{x.doi||"未提供"}</p>
           {x.abstract&&<p className="discovery-abstract">{x.abstract.slice(0,390)}{x.abstract.length>390?"…":""}</p>}
           <p className="small muted">{x.score_reason}</p>
           <p className="small muted">检索：{x.matched_queries.join("；")}</p>
           <div className="discovery-actions"><small>{x.status==="pending"?"待团队审核":x.status==="relevant"?"已纳入文献库":x.status==="method"?"已标注方法迁移":"已排除"}</small>
             {canEdit&&x.status==="pending"&&<div className="inline-actions">
               <button className="btn btn-secondary" disabled={busy} onClick={()=>void reviewPaper(x,"relevant")}><CheckCircle2 size={14}/> 相关</button>
               <button className="btn btn-secondary" disabled={busy} onClick={()=>void reviewPaper(x,"method")}><Lightbulb size={14}/> 方法借鉴</button>
               <button className="btn btn-secondary" disabled={busy} onClick={()=>void reviewPaper(x,"rejected")}><XCircle size={14}/> 排除</button>
             </div>}
           </div>
         </article>)}
       </div>
     </>}
   </section>
   <p className="small muted"><ShieldCheck size={14} style={{verticalAlign:"middle"}}/> 关联和推荐评分是可解释的初筛，不是数据质量验证。每日任务运行在免费实例上，休眠或重启可能中断；没有启用 LLM 推理费用。</p>
 </div>;
}
