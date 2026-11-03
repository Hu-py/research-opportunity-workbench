"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowRight, ArrowUpRight, BookOpen, BrainCircuit, CheckCircle2,
  ChevronDown, Clock3, Database, FileText, GitBranch, KeyRound, Layers3,
  Lightbulb, Loader2, LockKeyhole, LogOut, Menu, Play, Plus, RefreshCw,
  Search, Settings2, ShieldCheck, Sparkles, Workflow, X,
} from "lucide-react";
import { api } from "@/lib/api";
import type {Idea, Overview, Paper, Profile, Task, TaskEvent} from "@/lib/types";

type Section = "overview"|"papers"|"ideas"|"agent"|"history"|"profile"|"brief"|"settings";
const nav:{key:Section;label:string;caption:string;icon:typeof BookOpen}[] = [
  {key:"overview",label:"科研总览",caption:"Overview",icon:Layers3},
  {key:"papers",label:"论文情报库",caption:"Literature",icon:BookOpen},
  {key:"ideas",label:"研究选题池",caption:"Opportunities",icon:Lightbulb},
  {key:"agent",label:"Research Agent",caption:"Intelligent research",icon:BrainCircuit},
  {key:"history",label:"选题演化",caption:"Evolution",icon:GitBranch},
  {key:"profile",label:"研究者画像",caption:"Research profile",icon:ShieldCheck},
  {key:"brief",label:"每周科研简报",caption:"Weekly brief",icon:FileText},
  {key:"settings",label:"系统状态",caption:"System",icon:Settings2},
];
const statuses:Record<string,string>={
  candidate:"待评估",watch:"持续关注",shortlist:"重点选题",
  experiment:"实验准备",rejected:"暂不考虑",archived:"已归档",
};
const defaultProfile:Profile={
  goals:"发现城市科学与计算机方法交叉的、可被实验验证的研究机会",
  excluded_terms:[],
  research_lines:[{
    id:"urban_function",
    name:"城市三维功能研究（示例）",
    problem:"建筑内部功能标签稀疏，跨时间识别和泛化难",
    keywords:["urban","graph","building"],
    search_queries:["urban function mapping","building functional classification"],
    method_queries:["self-supervised graph learning","spatiotemporal representation learning"],
  }],
};

function dateLabel(raw?:string) {
  if (!raw) return "未记录";
  const parsed=new Date(raw);
  return Number.isNaN(parsed.getTime()) ? raw : parsed.toLocaleDateString("zh-CN",{month:"short",day:"numeric"});
}
function short(s:string,max=120){return s.length>max?s.slice(0,max)+"…":s}
function IconBtn({children,onClick,disabled,className=""}:{children:React.ReactNode;onClick:()=>void;disabled?:boolean;className?:string}){
  return <button type="button" className={"btn "+className} onClick={onClick} disabled={disabled}>{children}</button>;
}
function Empty({icon:Icon=Database,title,body,action}:{icon?:typeof Database;title:string;body:string;action?:React.ReactNode}){
  return <div className="empty"><Icon size={28} strokeWidth={1.5}/><h3>{title}</h3><p>{body}</p>{action}</div>;
}
function StatusBadge({status}:{status:string}){
  return <span className={"status status-"+status}>{statuses[status]||status}</span>;
}
function Spinner(){return <Loader2 size={17} className="spin"/>;}
function EvidenceList({papers}:{papers:Paper[]}){
  if (!papers.length) return <p className="small muted">尚无论文证据。请先执行文献检索。</p>;
  return <div className="evidence-list">{papers.map(p=><div className="evidence" key={p.id}>
    <div><strong>{p.title}</strong><span>{p.venue||"来源待核验"} · {p.published||"日期未知"}</span></div>
    {p.url&&<a target="_blank" rel="noopener noreferrer" href={p.url} aria-label="打开论文"><ArrowUpRight size={16}/></a>}
  </div>)}</div>;
}

export default function Workbench(){
  const [auth,setAuth]=useState<boolean|null>(null);
  const [loginPassword,setLoginPassword]=useState("");
  const [loginBusy,setLoginBusy]=useState(false);
  const [section,setSection]=useState<Section>("overview");
  const [mobileOpen,setMobileOpen]=useState(false);
  const [overview,setOverview]=useState<Overview|null>(null);
  const [papers,setPapers]=useState<Paper[]>([]);
  const [ideas,setIdeas]=useState<Idea[]>([]);
  const [tasks,setTasks]=useState<Task[]>([]);
  const [profile,setProfile]=useState<Profile|null>(null);
  const [brief,setBrief]=useState("");
  const [loading,setLoading]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [paperSearch,setPaperSearch]=useState("");
  const [ideaStatus,setIdeaStatus]=useState("all");
  const [expandedIdea,setExpandedIdea]=useState<string|null>(null);
  const [feedbackNote,setFeedbackNote]=useState("");
  const [feedbackStatus,setFeedbackStatus]=useState("watch");
  const [historyId,setHistoryId]=useState("");
  const [historyEvents,setHistoryEvents]=useState<TaskEvent[]|null>(null);
  const [profileText,setProfileText]=useState("");
  const [question,setQuestion]=useState("");
  const [selectedTaskId,setSelectedTaskId]=useState("");
  const selectedTask=tasks.find(t=>t.id===selectedTaskId)||null;

  const load=useCallback(async()=>{
    setLoading(true);setError("");
    const result=await Promise.allSettled([
      api<Overview>("overview"),
      api<{items:Paper[]}>("papers?limit=300"),
      api<{items:Idea[]}>("ideas"),
      api<{items:Task[]}>("tasks"),
      api<{profile:Profile|null}>("profile"),
      api<{markdown:string}>("brief"),
    ]);
    const [a,b,c,d,e,f]=result;
    if(a.status==="fulfilled")setOverview(a.value);
    if(b.status==="fulfilled")setPapers(b.value.items);
    if(c.status==="fulfilled")setIdeas(c.value.items);
    if(d.status==="fulfilled")setTasks(d.value.items);
    if(e.status==="fulfilled"){
      setProfile(e.value.profile);
      setProfileText(JSON.stringify(e.value.profile||defaultProfile,null,2));
    }
    if(f.status==="fulfilled")setBrief(f.value.markdown);
    const fail=result.find(x=>x.status==="rejected");
    if(fail?.status==="rejected")setError(fail.reason instanceof Error?fail.reason.message:"部分数据加载失败");
    setLoading(false);
  },[]);

  useEffect(()=>{
    fetch("/api/session",{cache:"no-store"}).then(r=>r.json())
      .then(d=>setAuth(Boolean(d.authenticated))).catch(()=>setAuth(false));
  },[]);
  useEffect(()=>{if(auth)void load();},[auth,load]);

  useEffect(()=>{
    if(!auth || !tasks.some(t=>t.status==="queued"||t.status==="running"))return;
    const timer=setInterval(async()=>{
      try {
        const r=await api<{items:Task[]}>("tasks");
        setTasks(r.items);
        if (!r.items.some(t=>t.status==="queued"||t.status==="running")){
          void load();
        }
      } catch {}
    },3500);
    return()=>clearInterval(timer);
  },[auth,tasks,load]);

  const filteredPapers=useMemo(()=>papers.filter(p=>
    (p.title+" "+(p.abstract||"")+" "+(p.venue||"")).toLowerCase().includes(paperSearch.toLowerCase())
  ),[papers,paperSearch]);
  const filteredIdeas=useMemo(()=>ideas.filter(i=>ideaStatus==="all"||i.status===ideaStatus),[ideas,ideaStatus]);
  const changeSection=(next:Section)=>{setSection(next);setMobileOpen(false);setNotice("");};

  async function login(){
    setLoginBusy(true);setError("");
    try{
      const res=await fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:loginPassword})});
      const data=await res.json();
      if(!res.ok)throw new Error(data.detail||"登录失败");
      setAuth(true);setLoginPassword("");
    }catch(e){setError(e instanceof Error?e.message:"登录失败");}
    finally{setLoginBusy(false);}
  }
  async function logout(){
    await fetch("/api/logout",{method:"POST"});
    setAuth(false);setOverview(null);setProfile(null);setTasks([]);
  }
  async function submit(kind:Task["kind"],query=""){
    setBusy(true);setError("");setNotice("");
    try{
      const job=await api<Task>("tasks",{method:"POST",body:JSON.stringify({kind,query})});
      setSelectedTaskId(job.id);
      setTasks(prev=>[job,...prev.filter(t=>t.id!==job.id)]);
      if(kind==="explore")changeSection("agent");
      setNotice("任务已提交："+job.id.slice(0,8)+"。工作台会持续查询进度。");
    }catch(e){setError(e instanceof Error?e.message:"提交失败");}
    finally{setBusy(false);}
  }
  async function saveProfile(){
    setBusy(true);setError("");setNotice("");
    try{
      const data=JSON.parse(profileText);
      const r=await api<{profile:Profile}>("profile",{method:"PUT",body:JSON.stringify(data)});
      setProfile(r.profile);setNotice("研究者画像已保存到私有数据库。");
      void load();
    }catch(e){setError(e instanceof Error?e.message:"JSON 格式无效");}
    finally{setBusy(false);}
  }
  async function saveFeedback(idea:Idea){
    setBusy(true);setError("");setNotice("");
    try{
      await api("ideas/"+idea.id+"/feedback",{
        method:"POST",body:JSON.stringify({status:feedbackStatus,note:feedbackNote})
      });
      setFeedbackNote("");setExpandedIdea(null);setNotice("反馈已保存，选题版本已更新。");
      void load();
    }catch(e){setError(e instanceof Error?e.message:"更新失败");}
    finally{setBusy(false);}
  }
  async function selectHistory(id:string){
    setHistoryId(id);setHistoryEvents(null);
    try{
      const data=await api<{items:{version:number;action:string;created_at:string;detail:Record<string,unknown>}[]}>(
        "ideas/"+id+"/history");
      setHistoryEvents(data.items.map(e=>({
        at:e.created_at,step:"V"+e.version+" · "+e.action,
        detail:typeof e.detail.note==="string"?e.detail.note:
          typeof e.detail.status==="string"?"更新为 "+(statuses[e.detail.status]||e.detail.status):
          JSON.stringify(e.detail)
      })));
    }catch(e){setError(e instanceof Error?e.message:"读取历史失败");}
  }
  function downloadBrief(){
    const blob=new Blob([brief],{type:"text/markdown;charset=utf-8"});
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");a.href=url;a.download="research-brief.md";a.click();
    URL.revokeObjectURL(url);
  }
  if(auth===null)return <div className="screen-center"><Spinner/><span>正在加载科研工作台…</span></div>;
  if(!auth)return <div className="login-page">
    <div className="login-visual"><div className="login-emblem"><BrainCircuit size={34}/></div>
      <span className="overline">PERSONAL RESEARCH INTELLIGENCE</span>
      <h1>让每一篇论文，<br/>成为下一个研究机会。</h1>
      <p>跨领域知识发现 · 持续选题演化 · 可追溯科研 Agent</p>
      <div className="login-lines"><span/><span/><span/></div>
    </div>
    <div className="login-panel"><div className="login-card">
      <div className="lock"><LockKeyhole size={21}/></div>
      <h2>登录科研工作台</h2><p>这是个人科研空间，请输入访问密码。</p>
      <form onSubmit={e=>{e.preventDefault();void login();}}>
        <label htmlFor="pw">访问密码</label>
        <input id="pw" type="password" autoComplete="current-password" value={loginPassword} onChange={e=>setLoginPassword(e.target.value)} placeholder="输入工作台密码"/>
        {error&&<p className="error">{error}</p>}
        <button className="btn btn-primary wide" disabled={loginBusy} type="submit">
          {loginBusy?<Spinner/>:<ArrowRight size={16}/>}进入工作台
        </button>
      </form><p className="login-help">密码由部署方在环境变量中设置，前端不保存 API Key。</p>
    </div></div>
  </div>;

  const sectionLabel=nav.find(n=>n.key===section)?.label||"科研总览";
  return <div className="shell">
    {mobileOpen&&<div className="mobile-scrim" onClick={()=>setMobileOpen(false)}/>}
    <aside className={"sidebar "+(mobileOpen?"sidebar-open":"")}>
      <div className="brand"><div className="brand-mark"><BrainCircuit size={22}/></div>
        <div><strong>Research Atlas</strong><span>INTELLIGENCE WORKSPACE</span></div>
        <button className="close-mobile" onClick={()=>setMobileOpen(false)} aria-label="关闭导航"><X size={20}/></button>
      </div>
      <div className="sidebar-label">WORKSPACE</div>
      <nav>{nav.map(item=><button className={"nav-item "+(section===item.key?"nav-active":"")}
        key={item.key} onClick={()=>changeSection(item.key)}>
        <item.icon size={18} strokeWidth={1.8}/><span>{item.label}<small>{item.caption}</small></span>
        {section===item.key&&<div className="nav-dot"/>}
      </button>)}</nav>
      <div className="sidebar-bottom">
        <div className="status-panel"><span className="online-dot"/> <span>Research Agent</span>
          <small>服务状态取决于后端配置</small></div>
        <button className="account" onClick={()=>void logout()}><span className="avatar">R</span>
          <span>个人科研空间<small>退出登录</small></span><LogOut size={16}/></button>
      </div>
    </aside>
    <main className="main">
      <header className="topbar">
        <button className="menu-mobile" onClick={()=>setMobileOpen(true)} aria-label="打开导航"><Menu size={20}/></button>
        <div className="breadcrumb">WORKSPACE <span>/</span> {sectionLabel}</div>
        <div className="top-actions">
          <span className="top-badge"><span className="online-dot"/> 研究数据实时关联</span>
          <IconBtn className="icon-only" onClick={()=>void load()} disabled={loading} >
            {loading?<Spinner/>:<RefreshCw size={17}/>}
          </IconBtn>
        </div>
      </header>
      <div className="content">
        {error&&<div className="alert alert-error"><span>{error}</span><button onClick={()=>setError("")}><X size={15}/></button></div>}
        {notice&&<div className="alert alert-success"><CheckCircle2 size={16}/><span>{notice}</span><button onClick={()=>setNotice("")}><X size={15}/></button></div>}

        {section==="overview"&&<>
          <div className="hero-card">
            <div><span className="overline">RESEARCH INTELLIGENCE · WORKSPACE</span>
              <h1>探索下一个<span>研究机会。</span></h1>
              <p>让文献发现、方法迁移与研究选题成为一个持续演化的知识闭环。</p>
              <button className="btn btn-white" onClick={()=>changeSection("agent")}>
                <Sparkles size={17}/> 开始科研探索 <ArrowRight size={16}/>
              </button>
            </div><div className="hero-art"><div className="orbit one"/><div className="orbit two"/>
              <div className="orb orb-one"/><div className="orb orb-two"/><div className="orb orb-three"/>
              <div className="hero-center"><BrainCircuit size={40}/></div></div>
          </div>
          <div className="stats-grid">
            {[
              {icon:BookOpen,n:overview?.papers||0,label:"已收录论文",hint:"跨学科文献资产"},
              {icon:Lightbulb,n:overview?.ideas||0,label:"滚动研究选题",hint:"持续追踪与更新"},
              {icon:GitBranch,n:overview?.revisions||0,label:"选题演化记录",hint:"所有修订有据可查"},
              {icon:Layers3,n:overview?.research_lines||0,label:"研究方向",hint:"个人研究画像"},
            ].map(item=><div className="stat-card" key={item.label}>
              <div className="stat-icon"><item.icon size={19}/></div><div className="stat-number">{item.n}</div>
              <strong>{item.label}</strong><small>{item.hint}</small></div>)}
          </div>
          <div className="content-grid">
            <section className="panel">
              <div className="panel-header"><div><span className="panel-kicker">OPPORTUNITIES</span><h2>近期研究机会</h2></div>
                <button className="text-link" onClick={()=>changeSection("ideas")}>查看全部 <ArrowUpRight size={16}/></button></div>
              {!ideas.length?<Empty icon={Lightbulb} title="等待发现第一个选题"
                body="完善研究者画像并启动文献检索后，这里将展示可追溯的研究机会。"
                action={<IconBtn className="btn-primary" onClick={()=>changeSection("profile")}>完善研究画像 <ArrowRight size={16}/></IconBtn>}/>:ideas.slice(0,4).map(i=>
                <button key={i.id} className="opportunity-row" onClick={()=>{setExpandedIdea(i.id);changeSection("ideas");}}>
                  <div className="opportunity-icon"><Lightbulb size={19}/></div>
                  <div><strong>{i.title}</strong><small>{i.method} · v{i.version}</small></div>
                  <StatusBadge status={i.status}/><ArrowUpRight size={16}/>
                </button>)}
            </section>
            <section className="panel right-panel"><div className="panel-header"><div><span className="panel-kicker">QUICK ACTIONS</span><h2>科研任务</h2></div></div>
              <div className="quick-card"><div className="quick-icon"><Search size={18}/></div>
                <div><strong>更新论文情报</strong><p>抓取新论文并刷新方法候选</p></div>
                <IconBtn className="btn-secondary" onClick={()=>void submit("sync")} disabled={busy||!profile}><Play size={16}/></IconBtn></div>
              <div className="quick-card"><div className="quick-icon lavender"><BrainCircuit size={18}/></div>
                <div><strong>启动科研 Agent</strong><p>探索新研究问题及方法迁移</p></div>
                <IconBtn className="btn-secondary" onClick={()=>changeSection("agent")}><ArrowRight size={16}/></IconBtn></div>
              <div className="quick-card"><div className="quick-icon teal"><FileText size={18}/></div>
                <div><strong>更新研究周报</strong><p>汇总新增文献与选题证据</p></div>
                <IconBtn className="btn-secondary" onClick={()=>void submit("weekly")} disabled={busy||!profile}><Play size={16}/></IconBtn></div>
              <div className="small-note"><ShieldCheck size={15}/> 推荐内容必须通过论文证据与人工验证。</div>
            </section>
          </div>
          <section className="panel">
            <div className="panel-header"><div><span className="panel-kicker">LITERATURE FEED</span><h2>近期收录文献</h2></div>
              <button className="text-link" onClick={()=>changeSection("papers")}>查看论文库 <ArrowRight size={16}/></button></div>
            {!papers.length?<Empty icon={BookOpen} title="论文库仍为空" body="完成首次数据采集后，新文献会出现在这里。"/>:papers.slice(0,5).map(p=>
            <div className="paper-row" key={p.id}><div className="paper-icon"><BookOpen size={17}/></div>
              <div><strong>{p.title}</strong><small>{p.venue||"来源待核验"} · {p.published||"未记录日期"}</small></div>
              {p.url&&<a target="_blank" rel="noopener noreferrer" href={p.url} aria-label="查看原文"><ArrowUpRight size={18}/></a>}
            </div>)}
          </section>
        </>}

        {section==="papers"&&<>
          <PageHeading kicker="LITERATURE INTELLIGENCE" title="论文情报库" subtitle="跨学科论文的长期积累：保留标题、摘要、来源和研究主题关联。"/>
          <div className="toolbar"><div className="searchbox"><Search size={18}/><input aria-label="搜索论文" placeholder="搜索论文标题、摘要、期刊或方法…" value={paperSearch} onChange={e=>setPaperSearch(e.target.value)}/></div>
            <span className="counter">{filteredPapers.length} 篇论文</span>
            <IconBtn onClick={()=>void submit("sync")} disabled={!profile||busy} className="btn-primary"><RefreshCw size={16}/> 更新论文</IconBtn></div>
          {!filteredPapers.length?<Empty icon={BookOpen} title={paperSearch?"没有匹配论文":"还没有论文"} body="修改搜索词，或者先建立研究者画像并执行文献采集。"/>:
            <div className="paper-grid">{filteredPapers.slice(0,150).map(p=><article className="paper-card" key={p.id}>
              <div className="paper-label"><span>ACADEMIC PAPER</span><span>{p.published?.slice(0,4)||"—"}</span></div>
              <h3>{p.title}</h3><p>{p.abstract?short(p.abstract,210):"OpenAlex 暂无可用摘要；请打开原文核验研究内容。"}</p>
              <div className="paper-foot"><span>{p.venue||"期刊或会议待核验"}</span>
                {p.url&&<a target="_blank" rel="noopener noreferrer" href={p.url}>原文 <ArrowUpRight size={15}/></a>}</div></article>)}</div>}
        </>}

        {section==="ideas"&&<>
          <PageHeading kicker="RESEARCH OPPORTUNITIES" title="滚动研究选题池" subtitle="选题不会每周重新清零。新证据、方法和人工反馈都会持续更新同一条选题记录。"/>
          <div className="toolbar">
            <div className="filter-pills">{[{k:"all",n:"全部"},...Object.entries(statuses).map(([k,n])=>({k,n}))].map(x=>
              <button key={x.k} className={"filter-pill "+(ideaStatus===x.k?"filter-active":"")} onClick={()=>setIdeaStatus(x.k)}>{x.n}</button>)}</div>
            <span className="counter">{filteredIdeas.length} 个方向</span>
          </div>
          {!filteredIdeas.length?<Empty icon={Lightbulb} title="暂无符合条件的选题" body="执行科研检索并审查证据后，这里会展示研究假设。"/>:filteredIdeas.map(idea=>
          <article className="idea-card" key={idea.id}>
            <div className="idea-main"><div className="idea-heading">
              <div><span className="mini-label">RESEARCH IDEA · V{idea.version}</span><h3>{idea.title}</h3></div>
              <span className="idea-score">{Math.round(idea.score)} <small>/100 初筛分</small></span></div>
              <div className="idea-tags"><StatusBadge status={idea.status}/><span className="method-chip">{idea.method}</span></div>
              <p>{idea.hypothesis}</p>
              <div className="idea-foot"><span><BookOpen size={15}/>{idea.papers.length} 篇关联论文</span>
                <button onClick={()=>{
                  if(expandedIdea===idea.id)setExpandedIdea(null);
                  else {setExpandedIdea(idea.id);setFeedbackStatus(idea.status);}
                }}>{expandedIdea===idea.id?"收起详情":"证据与反馈"} <ChevronDown size={16}/></button></div>
            </div>
            {expandedIdea===idea.id&&<div className="idea-expand">
              <div className="warning-note"><ShieldCheck size={16}/><span>{idea.caveat}</span></div>
              <h4>已关联的原始论文</h4><EvidenceList papers={idea.papers}/>
              <h4>研究者反馈</h4>
              <div className="feedback-grid"><label>选题状态<select value={feedbackStatus} onChange={e=>setFeedbackStatus(e.target.value)}>
                {Object.entries(statuses).map(([s,label])=><option key={s} value={s}>{label}</option>)}</select></label>
                <label>反馈备注<input value={feedbackNote} onChange={e=>setFeedbackNote(e.target.value)} placeholder="例如：已有数据可以先开展消融实验"/></label>
                <IconBtn className="btn-primary" disabled={busy} onClick={()=>void saveFeedback(idea)}>保存反馈</IconBtn></div>
            </div>}
          </article>)}
        </>}

        {section==="agent"&&<>
          <PageHeading kicker="RESEARCH AGENT" title="智能科研探索" subtitle="Research Agent 可以检索论文、查询你的知识库和已有选题，并输出待验证的研究建议与执行过程。"/>
          <div className="agent-grid">
            <div className="agent-main panel">
              <div className="agent-icon"><BrainCircuit size={25}/></div>
              <h2>你想探索什么研究问题？</h2>
              <p className="muted">尽量描述研究对象、现有数据、当前瓶颈与希望迁移的方法。</p>
              <textarea className="prompt" rows={6} maxLength={2000} value={question} onChange={e=>setQuestion(e.target.value)}
                placeholder="例如：我有多期建筑功能和路网数据，希望研究图神经网络如何提升跨时间的建筑垂直功能识别，请检索相关方法，并提出三个可验证的选题假设。"/>
              <div className="prompt-bottom"><span>{question.length}/2000</span>
                <IconBtn className="btn-primary" disabled={busy||question.trim().length<6} onClick={()=>void submit("explore",question)}>
                  {busy?<Spinner/>:<Sparkles size={17}/>} 发起科研任务 <ArrowRight size={16}/>
                </IconBtn></div>
              <div className="prompt-examples">
                <span>试试这些问题</span>
                {["少标签城市图学习有哪些最新方法？","多智能体如何用于动态水系统调度？","如何评估跨区域模型迁移和可信度？"].map(x=>
                  <button key={x} onClick={()=>setQuestion(x)}>{x} <ArrowUpRight size={13}/></button>)}
              </div>
            </div>
            <aside className="panel agent-side">
              <span className="panel-kicker">EXECUTION ENGINE</span><h2>Agent 工具链</h2>
              {[{n:"读取研究画像",d:"结合数据资产与研究瓶颈",icon:ShieldCheck},
                {n:"检索已有论文库",d:"寻找内部文献证据",icon:Database},
                {n:"实时 OpenAlex 检索",d:"获取新论文与原始出处",icon:Search},
                {n:"回看历史选题",d:"降低重复推荐",icon:GitBranch}].map(x=>
                <div className="tool-row" key={x.n}><div className="tool-icon"><x.icon size={17}/></div>
                <div><strong>{x.n}</strong><small>{x.d}</small></div></div>)}
              <div className="small-note"><ShieldCheck size={15}/> 选题创新性和论文结论仍需人工核验。</div>
            </aside>
          </div>
          <section className="panel task-panel">
            <div className="panel-header"><div><span className="panel-kicker">AGENT EXECUTION</span><h2>任务记录与研究结果</h2></div></div>
            <div className="task-chooser"><select aria-label="选择任务" value={selectedTaskId} onChange={e=>setSelectedTaskId(e.target.value)}>
              <option value="">选择一项任务查看进度</option>
              {tasks.map(t=><option value={t.id} key={t.id}>{t.kind==="explore"?"科研探索":t.kind==="weekly"?"研究周报":"文献更新"} · {t.id.slice(0,8)} · {t.status}</option>)}
            </select></div>
            {!selectedTask?<Empty icon={Workflow} title="尚未选择科研任务" body="上方提交研究问题后，这里将记录 Agent 的每次检索与执行结果。"/>:
            <div className="task-layout">
              <div><div className="task-status">
                <span className={"task-dot "+selectedTask.status}/><strong>{selectedTask.status==="completed"?"已完成":selectedTask.status==="failed"?"执行失败":selectedTask.status==="running"?"运行中":"排队等待"}</strong>
                <small>{selectedTask.id}</small></div>
                {selectedTask.status==="queued"&&<p className="small muted">任务正在等待独立 Worker。若长期停留，请确认云端 Worker 已启动。</p>}
                <h4>执行过程</h4>
                <div className="timeline">{selectedTask.events.length===0?<p className="small muted">等待后台任务启动…</p>:
                  selectedTask.events.map((event,i)=><div className="timeline-item" key={i}>
                    <div className="timeline-mark"/><div><strong>{event.step}</strong><p>{event.detail}</p><small>{dateLabel(event.at)}</small></div>
                  </div>)}</div>
              </div>
              <div className="agent-result"><h4>科研分析结果</h4>
                {selectedTask.error&&<div className="alert alert-error">{selectedTask.error}</div>}
                {selectedTask.result.answer?<div className="result-text">{selectedTask.result.answer}</div>:
                  <p className="muted small">结果尚未生成。</p>}
                {selectedTask.result.mode&&<div className="result-meta">运行模式：{selectedTask.result.mode}</div>}
                {!!selectedTask.result.sources?.length&&<><h4>本次涉及的论文来源</h4><EvidenceList papers={selectedTask.result.sources}/></>}
              </div>
            </div>}
          </section>
        </>}

        {section==="history"&&<>
          <PageHeading kicker="RESEARCH EVOLUTION" title="选题演化时间线" subtitle="保留选题创建、证据扩充、研究者反馈的版本变化，避免每周重新生成相同内容。"/>
          <section className="panel"><label className="field-label">选择选题</label>
            <select className="select-block" value={historyId} onChange={e=>void selectHistory(e.target.value)}>
              <option value="">请选择要查看的研究选题</option>{ideas.map(i=><option key={i.id} value={i.id}>{i.title}</option>)}
            </select>
            {!historyId?<Empty icon={GitBranch} title="选择一个研究选题" body="系统将展示它从生成到更新的全部版本记录。"/>:
              historyEvents===null?<div className="loading-row"><Spinner/>加载版本记录…</div>:
              <div className="timeline timeline-wide">{historyEvents.map((ev,i)=><div className="timeline-item" key={i}>
                <div className="timeline-mark"/><div><strong>{ev.step}</strong><p>{ev.detail}</p><small>{ev.at}</small></div>
              </div>)}</div>}
          </section>
        </>}

        {section==="profile"&&<>
          <PageHeading kicker="RESEARCHER PROFILE" title="研究者画像" subtitle="描述你正在解决的问题、已有数据和方法能力；这些内容只存储在配置的科研数据库中。"/>
          <div className="content-grid"><section className="panel">
            <div className="panel-header"><div><span className="panel-kicker">ACTIVE RESEARCH</span><h2>研究主线</h2></div></div>
            {!profile?<Empty icon={ShieldCheck} title="尚未建立个人科研画像" body="右侧已提供一份可编辑示例，修改后点击保存。"/>:
              profile.research_lines.map(line=><div className="line-card" key={line.id}>
                <div className="line-icon"><Layers3 size={20}/></div><div><h3>{line.name}</h3><p>{line.problem}</p>
                <small>{line.method_queries.join(" · ")}</small></div></div>)}
          </section>
          <section className="panel">
            <div className="panel-header"><div><span className="panel-kicker">PROFILE EDITOR</span><h2>管理研究画像</h2></div></div>
            <p className="small muted">当前支持结构化 JSON 编辑。简历、论文与其他材料导入将在下一阶段接入。</p>
            <textarea className="code-editor" spellCheck={false} value={profileText} onChange={e=>setProfileText(e.target.value)} rows={19}/>
            <div className="panel-actions"><IconBtn className="btn-primary" disabled={busy} onClick={()=>void saveProfile()}>
              <CheckCircle2 size={16}/> 验证并保存
            </IconBtn></div>
          </section></div>
        </>}

        {section==="brief"&&<>
          <PageHeading kicker="WEEKLY RESEARCH BRIEF" title="每周科研简报" subtitle="总结新论文和选题库的变化，并保留可追溯的原始出处。"/>
          <section className="panel">
            <div className="panel-header"><div><span className="panel-kicker">RESEARCH DIGEST</span><h2>当前报告</h2></div>
              <div className="inline-actions"><IconBtn onClick={()=>void submit("weekly")} disabled={!profile||busy}><RefreshCw size={15}/> 重新生成</IconBtn>
              <IconBtn onClick={downloadBrief} disabled={!brief} className="btn-primary"><FileText size={16}/> 下载 .md</IconBtn></div></div>
            {!brief?<Empty icon={FileText} title="目前没有简报" body="先保存研究者画像并运行论文采集，即可获得初版简报。"/>:
              <pre className="brief-text">{brief}</pre>}
          </section>
        </>}

        {section==="settings"&&<>
          <PageHeading kicker="SYSTEM STATUS" title="系统与运行状态" subtitle="查看研究数据库、模型调用和自动化任务的配置状态。"/>
          <div className="settings-grid">
            {[{icon:Database,title:"科研数据库",detail:"论文、画像、选题与任务结果持久化到后端数据库",flag:"已连接数量："+(overview?.papers||0)},
              {icon:BrainCircuit,title:"Research Agent",detail:"配置 OPENAI_API_KEY 后启动真实模型工具调用；否则只进行文献预览",flag:"模型配置由后端管理"},
              {icon:Workflow,title:"任务 Worker",detail:"生产环境需运行独立 worker 进程，以处理排队中的长任务",flag:"待执行："+tasks.filter(x=>x.status==="queued").length},
              {icon:ShieldCheck,title:"访问控制",detail:"浏览器访问与后端 API 分开认证；密钥仅存于服务端",flag:"单用户实验版"}].map(x=>
              <div className="panel settings-card" key={x.title}><div className="tool-icon"><x.icon size={22}/></div>
                <h3>{x.title}</h3><p>{x.detail}</p><span>{x.flag}</span></div>)}
          </div>
          <section className="panel"><h2>上线前配置</h2><p className="small muted">
            需要分别设置前端的 APP_PASSWORD、SESSION_SECRET、BACKEND_URL、API_BEARER_TOKEN，
            以及后端的 APP_ENV、DATABASE_URL、API_BEARER_TOKEN。模型密钥只放后端。公开仓库不得包含个人未发表资料与密钥。
          </p></section>
        </>}
      </div>
      <footer className="footer"><span>RESEARCH ATLAS · WORKBENCH V0.2</span>
        <span>Evidence before innovation claims · © Research Atlas</span></footer>
    </main>
  </div>;
}

function PageHeading({kicker,title,subtitle}:{kicker:string;title:string;subtitle:string}){
  return <div className="page-heading"><span className="panel-kicker">{kicker}</span>
    <h1>{title}</h1><p>{subtitle}</p></div>;
}
