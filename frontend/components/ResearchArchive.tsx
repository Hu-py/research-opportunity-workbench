"use client";

import {useCallback,useEffect,useMemo,useState} from "react";
import {ArrowUpRight,BookMarked,CheckCircle2,Clock3,RefreshCw,Search,ShieldCheck,XCircle} from "lucide-react";
import {api} from "@/lib/api";

type Output={
  id:string;kind:string;owner:string;title:string;year:number;authors:string;venue:string;
  doi:string;url:string;source_url:string;source_kind:string;status:string;tags:string[];
};
type RefreshRun={id:string;status:string;source:string;scanned:number;inserted:number;error:string;created_at:string};
export default function ResearchArchive({canAdmin}:{canAdmin:boolean}){
  const [items,setItems]=useState<Output[]>([]);
  const [runs,setRuns]=useState<RefreshRun[]>([]);
  const [filter,setFilter]=useState<"verified"|"review"|"all">("verified");
  const [kind,setKind]=useState<"all"|"paper"|"project">("all");
  const [search,setSearch]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");

  const load=useCallback(async()=>{
    const [output,history]=await Promise.all([
      api<{items:Output[]}>("team-repository"),
      api<{items:RefreshRun[]}>("team-repository/refresh-runs"),
    ]);
    setItems(output.items);setRuns(history.items);
  },[]);

  useEffect(()=>{void load().catch(e=>setError(String(e)));},[load]);
  useEffect(()=>{
    if(!runs.some(x=>x.status==="queued"||x.status==="running"))return;
    const interval=setInterval(()=>{void load().catch(()=>{});},4500);
    return()=>clearInterval(interval);
  },[runs,load]);

  async function refresh(){
    setBusy(true);setError("");setNotice("");
    try{
      const r=await api<{id:string}>("team-repository/refresh",{method:"POST"});
      setNotice("增量扫描已启动（"+r.id.slice(0,8)+"）。新发现论文将先进入“待核验”，不会直接作为团队正式成果。");
      await load();
    }catch(e){setError(e instanceof Error?e.message:String(e));}
    finally{setBusy(false);}
  }
  async function review(id:string,status:"verified"|"rejected"){
    setBusy(true);setError("");
    try{
      const record=await api<Output>("team-repository/"+id,{method:"PATCH",body:JSON.stringify({status})});
      setItems(old=>old.map(x=>x.id===record.id?record:x));
      setNotice(status==="verified"?"成果已通过核验。":"已将该条记录排除出正式成果列表。");
    }catch(e){setError(e instanceof Error?e.message:String(e));}
    finally{setBusy(false);}
  }
  const visible=useMemo(()=>items.filter(x=>
    (filter==="all"||x.status===filter) && (kind==="all"||x.kind===kind)
    && (x.title+" "+x.authors+" "+x.venue+" "+x.tags.join(" ")).toLowerCase().includes(search.trim().toLowerCase())
  ),[items,filter,kind,search]);
  const verified=items.filter(x=>x.status==="verified").length;
  const reviewCount=items.filter(x=>x.status==="review").length;
  const latest=runs[0];
  return <div className="repository-root">
    <div className="page-heading"><span className="panel-kicker">TEAM KNOWLEDGE BASE</span>
      <h1>团队既有研究成果</h1>
      <p>同济大学沈尧老师公开论文与课题成果，作为后续 Research Agent 理解团队积累的证据底板。</p>
    </div>
    <div className="repository-stat-row">
      <div><strong>{verified}</strong><span>已核验成果</span></div>
      <div><strong>{items.filter(x=>x.kind==="paper"&&x.status==="verified").length}</strong><span>论文与文章</span></div>
      <div><strong>{items.filter(x=>x.kind==="project"&&x.status==="verified").length}</strong><span>科研项目</span></div>
      <div><strong>{reviewCount}</strong><span>新增待核验</span></div>
    </div>
    <section className="panel repository-intro">
      <div className="repository-topline">
        <div><div className="panel-kicker">AUTHORITY & PROVENANCE</div>
          <h2>沈尧 · SHEN Yao</h2>
          <p className="muted small">同济大学建筑与城市规划学院 · 城市科学与规划中心 · ORCID 0000-0002-7261-4234</p>
          <p className="small">来源以同济大学师资主页与期刊出版页为准；2025–2026 年新增成果单独核实。非完整成果清单。</p>
          <a href="https://caupzs.tongji.edu.cn/e3/c0/c19001a189376/page.htm" target="_blank" rel="noopener noreferrer" className="repository-source">
            查看官方师资成果目录 <ArrowUpRight size={14}/>
          </a>
        </div>
        <div className="repository-refresh">
          <button className="btn btn-primary" disabled={!canAdmin||busy} onClick={()=>void refresh()}>
            <RefreshCw size={15}/> {busy?"正在请求":"立即检查新成果"}
          </button>
          <small>自动发现采用 ORCID 精确过滤；同名作者不会直接进入已核验列表。</small>
        </div>
      </div>
      {latest&&<p className="repository-sync-line"><Clock3 size={14}/> 最近扫描：
        {latest.status==="completed"?"完成":latest.status==="failed"?"失败":latest.status==="running"?"运行中":"排队中"}
        {latest.status==="completed"?" · 检查 "+latest.scanned+" 条 · 新发现 "+latest.inserted+" 条":""}
        {latest.error?" · "+latest.error:""}
      </p>}
    </section>
    {error&&<div className="alert alert-error">{error}</div>}
    {notice&&<div className="alert alert-success">{notice}</div>}
    <section className="panel">
      <div className="repository-filters">
        <div className="searchbox"><Search size={16}/><input aria-label="搜索团队成果" placeholder="搜索论文、作者、关键词…" value={search} onChange={e=>setSearch(e.target.value)}/></div>
        <select aria-label="核验状态" value={filter} onChange={e=>setFilter(e.target.value as typeof filter)}>
          <option value="verified">已核验</option><option value="review">待核验（{reviewCount}）</option><option value="all">全部状态</option>
        </select>
        <select aria-label="成果类型" value={kind} onChange={e=>setKind(e.target.value as typeof kind)}>
          <option value="all">论文与课题</option><option value="paper">论文/文章</option><option value="project">科研项目</option>
        </select>
        <span className="counter">{visible.length} 项</span>
      </div>
      {!visible.length?<div className="empty"><BookMarked size={27}/><h3>暂无匹配成果</h3><p>你可以调整筛选条件或手动检查新成果。</p></div>:
      <div className="repository-list">{visible.map(x=><article className="repository-item" key={x.id}>
        <div className="repository-item-title">
          <span className="repository-year">{x.year}</span>
          <span className="repository-kind">{x.kind==="project"?"科研课题":"论文/文章"}</span>
          {x.status==="review"&&<span className="repository-pending">待核验</span>}
          {x.status==="verified"&&<span className="repository-verified"><ShieldCheck size={12}/> 已核验</span>}
          {x.status==="rejected"&&<span className="repository-pending">已排除</span>}
        </div>
        <h3>{x.title}</h3>
        <p className="small muted">{x.venue}{x.authors?" · "+x.authors:""}</p>
        <div className="repository-item-bottom">
          <div className="repository-tags">{x.tags.slice(0,3).map(tag=><span key={tag}>{tag}</span>)}</div>
          <div className="inline-actions">
            {x.url&&<a className="repository-source" href={x.url} target="_blank" rel="noopener noreferrer">成果链接 <ArrowUpRight size={14}/></a>}
            {x.source_url&&<a className="repository-source" href={x.source_url} target="_blank" rel="noopener noreferrer">核验来源 <ArrowUpRight size={14}/></a>}
            {canAdmin&&x.status==="review"&&<>
              <button className="btn btn-secondary" disabled={busy} onClick={()=>void review(x.id,"verified")}><CheckCircle2 size={14}/> 确认</button>
              <button className="btn btn-secondary" disabled={busy} onClick={()=>void review(x.id,"rejected")}><XCircle size={14}/> 排除</button>
            </>}
          </div>
        </div>
      </article>)}</div>}
    </section>
  </div>;
}
