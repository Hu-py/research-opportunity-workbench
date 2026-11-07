"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowRight, ArrowUpRight, BookOpen, BrainCircuit, CheckCircle2,
  ChevronDown, Clock3, Database, FileText, GitBranch, KeyRound, Layers3,
  Lightbulb, Loader2, LockKeyhole, LogOut, Menu, Play, Plus, RefreshCw,
  Search, Settings2, ShieldCheck, Sparkles, Workflow, X,
} from "lucide-react";
import { api } from "@/lib/api";
import ResearchArchive from "@/components/ResearchArchive";
import DataAssetRegistry from "@/components/DataAssetRegistry";
import ResearchDiscovery from "@/components/ResearchDiscovery";
import AIResearchLab from "@/components/AIResearchLab";
import ModelSettings from "@/components/ModelSettings";
import ResearchRadar from "@/components/ResearchRadar";
import ResearchProfileStudio from "@/components/ResearchProfileStudio";
import InterestWatchlist from "@/components/InterestWatchlist";
import AcademicSourceRegistry from "@/components/AcademicSourceRegistry";
import AgentGameReplay from "@/components/AgentGameReplay";
import type {Idea, Overview, Paper, Profile, Task, TaskEvent, TeamMember, TeamAudit} from "@/lib/types";

type Section = "interest"|"profile-draft"|"profile-skill"|"overview"|"papers"|"repository"|"assets"|"discovery"|"ai-lab"|"radar"|"ideas"|"agent"|"history"|"profile"|"brief"|"settings"|"sources"|"game-lab";
type NavEntry = {key:Section;label:string;icon:typeof BookOpen};
const navigationGroups:{label:string;items:NavEntry[]}[] = [
  {label:"工作台",items:[
    {key:"overview",label:"科研总览",icon:Layers3},
  ]},
  {label:"研究基础",items:[
    {key:"profile",label:"团队画像",icon:ShieldCheck},
    {key:"papers",label:"科研资源库",icon:Database},
  ]},
  {label:"学术基础",items:[
    {key:"sources",label:"学术来源管理",icon:BookOpen},
  ]},
  {label:"研究发现",items:[
    {key:"discovery",label:"文献发现",icon:Search},
    {key:"ideas",label:"选题中心",icon:Lightbulb},
  ]},
  {label:"研究执行",items:[
    {key:"agent",label:"Research Agent",icon:BrainCircuit},
    {key:"game-lab",label:"多智能体博弈回放",icon:GitBranch},
  ]},
  {label:"研究产出",items:[
    {key:"brief",label:"科研简报",icon:FileText},
  ]},
];

// All original feature routes remain available as secondary navigation.
const moduleTabs:Partial<Record<Section,{title:string;items:{key:Section;label:string}[]}>> = {
  profile:{title:"团队画像与研究方向",items:[
    {key:"profile",label:"正式画像"},
    {key:"profile-draft",label:"数据画像"},
    {key:"interest",label:"研究兴趣"},
    {key:"profile-skill",label:"画像更新"},
  ]},
  papers:{title:"科研资源库",items:[
    {key:"papers",label:"论文情报"},
    {key:"repository",label:"团队成果"},
    {key:"assets",label:"数据台账"},
  ]},
  ideas:{title:"选题中心",items:[
    {key:"ideas",label:"研究选题池"},
    {key:"ai-lab",label:"AI 选题分析"},
    {key:"radar",label:"科研雷达与评审"},
    {key:"history",label:"选题演化"},
  ]},
};
const parentSections:Partial<Record<Section,Section>> = {
  "profile-draft":"profile","profile-skill":"profile",interest:"profile",
  repository:"papers",assets:"papers",
  "ai-lab":"ideas",radar:"ideas",history:"ideas",
};
function primarySection(current:Section):Section {
  return parentSections[current]||current;
}
const statuses:Record<string,string>={
  candidate:"待评估",watch:"持续关注",shortlist:"重点选题",
  experiment:"实验准备",rejected:"暂不考虑",archived:"已归档",
};
const defaultProfile:Profile={
  goals:"让团队共同发现城市科学与计算机方法交叉的科研机会",
  team:{name:"科研团队（示例）",mission:"通过跨学科协作发现有依据、可验证的研究方向",priorities:["可验证的研究创新"]},
  datasets:[],
  methods:[],
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
  const [loginEmail,setLoginEmail]=useState("");
  const [teamMode,setTeamMode]=useState(false);
  const [member,setMember]=useState<TeamMember|null>(null);
  const [members,setMembers]=useState<TeamMember[]>([]);
  const [audits,setAudits]=useState<TeamAudit[]>([]);
  const [inviteEmail,setInviteEmail]=useState("");
  const [inviteName,setInviteName]=useState("");
  const [invitePassword,setInvitePassword]=useState("");
  const [inviteRole,setInviteRole]=useState<"admin"|"researcher"|"viewer">("researcher");
  const [profileVersion,setProfileVersion]=useState(0);
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
  const canAdmin=!teamMode || member?.role==="admin";
  const canEdit=!teamMode || member?.role==="admin" || member?.role==="researcher";

  const load=useCallback(async()=>{
    setLoading(true);setError("");
    const result=await Promise.allSettled([
      api<Overview>("overview"),
      api<{items:Paper[]}>("papers?limit=300"),
      api<{items:Idea[]}>("ideas"),
      api<{items:Task[]}>("tasks"),
      api<{profile:Profile|null;version?:number}>("profile"),
      api<{markdown:string}>("brief"),
    ]);
    const [a,b,c,d,e,f]=result;
    if(a.status==="fulfilled")setOverview(a.value);
    if(b.status==="fulfilled")setPapers(b.value.items);
    if(c.status==="fulfilled")setIdeas(c.value.items);
    if(d.status==="fulfilled")setTasks(d.value.items);
    if(e.status==="fulfilled"){
      setProfile(e.value.profile);
      setProfileVersion(e.value.version||0);
      setProfileText(JSON.stringify(e.value.profile||defaultProfile,null,2));
    }
    if(f.status==="fulfilled")setBrief(f.value.markdown);
    const fail=result.find(x=>x.status==="rejected");
    if(fail?.status==="rejected")setError(fail.reason instanceof Error?fail.reason.message:"部分数据加载失败");
    setLoading(false);
  },[]);

  useEffect(()=>{
    fetch("/api/session",{cache:"no-store"}).then(r=>r.json())
      .then(d=>{
        setTeamMode(Boolean(d.team));
        setMember(d.member||null);
        setAuth(Boolean(d.authenticated));
      }).catch(()=>setAuth(false));
  },[]);
  useEffect(()=>{if(auth)void load();},[auth,load]);
  useEffect(()=>{
    if(!auth || !teamMode || member?.role!=="admin")return;
    void Promise.allSettled([
      api<{items:TeamMember[]}>("team/members"),
      api<{items:TeamAudit[]}>("team/audit"),
    ]).then(([a,b])=>{
      if(a.status==="fulfilled")setMembers(a.value.items);
      if(b.status==="fulfilled")setAudits(b.value.items);
    });
  },[auth,teamMode,member?.role]);

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
      const res=await fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:loginPassword,email:loginEmail})});
      const data=await res.json();
      if(!res.ok)throw new Error(data.detail||"登录失败");
      setAuth(true);setLoginPassword("");if(data.member)setMember(data.member);
    }catch(e){setError(e instanceof Error?e.message:"登录失败");}
    finally{setLoginBusy(false);}
  }
  async function logout(){
    await fetch("/api/logout",{method:"POST"});
    setAuth(false);setOverview(null);setProfile(null);setTasks([]);setMember(null);setMembers([]);
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
      if(teamMode)data.expected_version=profileVersion;
      const r=await api<{profile:Profile;version:number}>("profile",{method:"PUT",body:JSON.stringify(data)});
      setProfile(r.profile);setProfileVersion(r.version||0);setNotice("团队研究画像已保存，新版本已写入数据库。");
      void load();
    }catch(e){setError(e instanceof Error?e.message:"JSON 格式无效");}
    finally{setBusy(false);}
  }
  async function inviteMember(){
    setBusy(true);setError("");setNotice("");
    try{
      const m=await api<TeamMember>("team/members",{
        method:"POST",
        body:JSON.stringify({email:inviteEmail,name:inviteName,
          temporary_password:invitePassword,role:inviteRole})
      });
      setMembers(prev=>[...prev,m]);
      setInviteEmail("");setInviteName("");setInvitePassword("");
      setNotice("成员已创建。请通过安全渠道单独告知其临时密码。");
    }catch(e){setError(e instanceof Error?e.message:"创建成员失败");}
    finally{setBusy(false);}
  }
  async function changeMember(m:TeamMember, active:boolean){
    setBusy(true);setError("");setNotice("");
    try{
      const updated=await api<TeamMember>("team/members/"+m.id,{
        method:"PATCH",body:JSON.stringify({active})
      });
      setMembers(prev=>prev.map(x=>x.id===updated.id?updated:x));
      setNotice("成员状态已更新，并保留操作审计记录。");
    }catch(e){setError(e instanceof Error?e.message:"更新失败");}
    finally{setBusy(false);}
  }

  async function dispatchExistingTask(task:Task){
    if(task.status!=="queued")return;
    setBusy(true);setError("");setNotice("");
    try{
      await api<Task>("tasks/"+task.id+"/dispatch",{method:"POST"});
      setNotice("已请求后台执行排队任务；免费测试环境可能在休眠或重启时中断任务。");
      void load();
    }catch(e){setError(e instanceof Error?e.message:"请求执行失败");}
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
      <span className="overline">TEAM RESEARCH INTELLIGENCE</span>
      <h1>让每一篇论文，<br/>成为下一个研究机会。</h1>
      <p>跨领域知识发现 · 持续选题演化 · 可追溯科研 Agent</p>
      <div className="login-lines"><span/><span/><span/></div>
    </div>
    <div className="login-panel"><div className="login-card">
      <div className="lock"><LockKeyhole size={21}/></div>
      <h2>登录科研工作台</h2><p>{teamMode?"使用团队成员邮箱和密码登录，共享科研知识库。":"请输入工作台访问密码。"}</p>
      <form onSubmit={e=>{e.preventDefault();void login();}}>
        {teamMode&&<><label htmlFor="email">团队成员邮箱</label>
        <input id="email" type="email" autoComplete="username" required value={loginEmail} onChange={e=>setLoginEmail(e.target.value)} placeholder="name@university.edu"/></>}
        <label htmlFor="pw">访问密码</label>
        <input id="pw" type="password" autoComplete="current-password" value={loginPassword} onChange={e=>setLoginPassword(e.target.value)} placeholder="输入工作台密码"/>
        {error&&<p className="error">{error}</p>}
        <button className="btn btn-primary wide" disabled={loginBusy} type="submit">
          {loginBusy?<Spinner/>:<ArrowRight size={16}/>}进入工作台
        </button>
      </form><p className="login-help">密码由部署方在环境变量中设置，前端不保存 API Key。</p>
    </div></div>
  </div>;

  const primary=primarySection(section);
  const currentModule=moduleTabs[primary];
  const primaryLabel=navigationGroups.flatMap(group=>group.items)
    .find(item=>item.key===primary)?.label||(primary==="settings"?"系统管理":"科研总览");
  const sectionLabel=currentModule?.items.find(tab=>tab.key===section)?.label||primaryLabel;
  return <div className="shell">
    {mobileOpen&&<div className="mobile-scrim" onClick={()=>setMobileOpen(false)}/>}
    <aside className={"sidebar "+(mobileOpen?"sidebar-open":"")}>
      <div className="brand"><div className="brand-mark"><BrainCircuit size={22}/></div>
        <div><strong>Research Atlas</strong><span>INTELLIGENCE WORKSPACE</span></div>
        <button className="close-mobile" onClick={()=>setMobileOpen(false)} aria-label="关闭导航"><X size={20}/></button>
      </div>
      <nav className="sidebar-nav" aria-label="科研工作台主导航">
        {navigationGroups.map(group=><div className="nav-group" key={group.label}>
          <div className="nav-group-title">{group.label}</div>
          {group.items.map(item=><button type="button"
            aria-current={primary===item.key?"page":undefined}
            className={"nav-item "+(primary===item.key?"nav-active":"")}
            key={item.key} onClick={()=>changeSection(item.key)}>
            <item.icon size={18} strokeWidth={1.8}/><span>{item.label}</span>
            {primary===item.key&&<div className="nav-dot"/>}
          </button>)}
        </div>)}
      </nav>
      <div className="sidebar-bottom">
        <div className="nav-group-title">管理</div>
        <button type="button" aria-current={section==="settings"?"page":undefined}
          className={"nav-item sidebar-settings "+(section==="settings"?"nav-active":"")}
          onClick={()=>changeSection("settings")}>
          <Settings2 size={18} strokeWidth={1.8}/><span>系统管理</span>
          {section==="settings"&&<div className="nav-dot"/>}
        </button>
        <div className="status-panel"><span className="online-dot"/> <span>Research Agent</span>
          <small>服务状态取决于后端配置</small></div>
        <button className="account" onClick={()=>void logout()}><span className="avatar">R</span>
          <span>{member?.name||"团队共享科研空间"}<small>{member?member.role+" · 退出登录":"退出登录"}</small></span><LogOut size={16}/></button>
      </div>
    </aside>
    <main className="main">
      <header className="topbar">
        <button className="menu-mobile" onClick={()=>setMobileOpen(true)} aria-label="打开导航"><Menu size={20}/></button>
        <div className="breadcrumb">WORKSPACE <span>/</span> {primaryLabel}{sectionLabel!==primaryLabel&&<><span>/</span> {sectionLabel}</>}</div>
        <div className="top-actions">
          <span className="top-badge"><span className="online-dot"/> 研究数据实时关联</span>
          <IconBtn className="icon-only" onClick={()=>void load()} disabled={loading} >
            {loading?<Spinner/>:<RefreshCw size={17}/>}
          </IconBtn>
        </div>
      </header>
      <div className="content">
        {currentModule&&<div className="module-switcher" aria-label={currentModule.title+"子页面"}>
          <div className="module-switcher-heading">
            <span className="module-eyebrow">WORKSPACE MODULE</span>
            <strong>{currentModule.title}</strong>
          </div>
          <nav className="module-tabs" aria-label={currentModule.title}>
            {currentModule.items.map(tab=><button type="button" key={tab.key}
              aria-current={section===tab.key?"page":undefined}
              className={"module-tab "+(section===tab.key?"module-tab-active":"")}
              onClick={()=>changeSection(tab.key)}>{tab.label}</button>)}
          </nav>
        </div>}
        {error&&<div className="alert alert-error"><span>{error}</span><button onClick={()=>setError("")}><X size={15}/></button></div>}
        {notice&&<div className="alert alert-success"><CheckCircle2 size={16}/><span>{notice}</span><button onClick={()=>setNotice("")}><X size={15}/></button></div>}

        {section==="interest"&&<InterestWatchlist canEdit={canEdit}/>}
        {section==="overview"&&<>
          <div className="hero-card">
            <div><span className="overline">RESEARCH INTELLIGENCE · WORKSPACE</span>
              <h1>探索下一个<span>研究机会。</span></h1>
              <p>让文献发现、方法迁移与研究选题成为一个持续演化的知识闭环。</p>
              <button className="btn btn-white" onClick={()=>changeSection("interest")}>
                <GitBranch size={17}/> 管理研究兴趣 <ArrowRight size={16}/>
              </button>
              <button className="btn btn-white" style={{marginLeft:9}} onClick={()=>changeSection("agent")}>
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
              {icon:Layers3,n:overview?.research_lines||0,label:"研究方向",hint:"共享团队画像"},
              {icon:Database,n:overview?.cusp_datasets||0,label:"CUSP既有数据",hint:"仅属性目录，不含源数据"},
            ].map(item=><button type="button" className="stat-card stat-card-interactive" key={item.label}
              title={item.label==="CUSP既有数据"?"查看已导入的 CUSP 数据属性台账":undefined}
              onClick={()=>changeSection(item.label==="CUSP既有数据"?"assets":item.label==="已收录论文"?"papers":item.label==="滚动研究选题"?"ideas":item.label==="研究方向"?"profile":"history")}>
              <div className="stat-icon"><item.icon size={19}/></div><div className="stat-number">{item.n}</div>
              <strong>{item.label}</strong><small>{item.hint}</small></button>)}
          </div>
          <div className="content-grid">
            <section className="panel">
              <div className="panel-header"><div><span className="panel-kicker">OPPORTUNITIES</span><h2>近期研究机会</h2></div>
                <button className="text-link" onClick={()=>changeSection("ideas")}>查看全部 <ArrowUpRight size={16}/></button></div>
              {!ideas.length?<Empty icon={Lightbulb} title="等待发现第一个选题"
                body="完善团队研究画像并启动文献检索后，这里将展示可追溯的研究机会。"
                action={<IconBtn className="btn-primary" onClick={()=>changeSection("profile")}>完善团队画像 <ArrowRight size={16}/></IconBtn>}/>:ideas.slice(0,4).map(i=>
                <button key={i.id} className="opportunity-row" onClick={()=>{setExpandedIdea(i.id);changeSection("ideas");}}>
                  <div className="opportunity-icon"><Lightbulb size={19}/></div>
                  <div><strong>{i.title}</strong><small>{i.method} · v{i.version}</small></div>
                  <StatusBadge status={i.status}/><ArrowUpRight size={16}/>
                </button>)}
            </section>
            <section className="panel right-panel"><div className="panel-header"><div><span className="panel-kicker">QUICK ACTIONS</span><h2>科研任务</h2></div></div>
              <div className="quick-card"><div className="quick-icon"><Search size={18}/></div>
                <div><strong>更新论文情报</strong><p>抓取新论文并刷新方法候选</p></div>
                <IconBtn className="btn-secondary" onClick={()=>void submit("sync")} disabled={busy||!profile||!canEdit}><Play size={16}/></IconBtn></div>
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

        {section==="repository"&&<ResearchArchive canAdmin={canAdmin}/>}
        {section==="assets"&&<DataAssetRegistry canAdmin={canAdmin}/>}
        {section==="sources"&&<AcademicSourceRegistry canAdmin={canAdmin}/>}
        {section==="discovery"&&<ResearchDiscovery canAdmin={canAdmin} canEdit={canEdit}/>} 
        {section==="ai-lab"&&<AIResearchLab canAdmin={canAdmin} canEdit={canEdit}/>} 
        {section==="game-lab"&&<AgentGameReplay/>}
        {section==="radar"&&<ResearchRadar canEdit={canEdit}/>} 

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
                <IconBtn className="btn-primary" disabled={busy||!canEdit} onClick={()=>void saveFeedback(idea)}>保存反馈</IconBtn></div>
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
                <IconBtn className="btn-primary" disabled={busy||!canEdit||question.trim().length<6} onClick={()=>void submit("explore",question)}>
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
              <div className="small-note"><ShieldCheck size={15}/> 未配置模型 API 时仅运行真实文献检索预览，不生成 LLM 分析；选题创新性仍需人工核验。</div>
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
                {selectedTask.status==="queued"&&<>
                  <p className="small muted">任务已写入共享数据库。免费测试环境采用现有 API 执行短任务；休眠或重启可能导致执行中断。</p>
                  {canEdit&&<IconBtn className="btn-secondary" disabled={busy} onClick={()=>void dispatchExistingTask(selectedTask)}>
                    <Play size={15}/> 重新启动排队任务
                  </IconBtn>}
                </>}
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

        {section==="profile-draft"&&<>
          <PageHeading kicker="DATABASE-SOURCED PORTRAIT" title="数据库初步科研画像" subtitle="来自团队数据库的科研方向初稿：可核查成果、研究主线、证据 ID、方法瓶颈和实验条件。尚未人工发布的内容不自动成为正式画像。"/>
          <ResearchProfileStudio canAdmin={canAdmin} onApplied={()=>void load()} view="draft"/>
        </>}
        {section==="profile-skill"&&<>
          <PageHeading kicker="REUSABLE RESEARCH PROFILE SKILL" title="科研画像更新 Skill" subtitle="基于 PostgreSQL 的事实约束、版本差异和审阅机制，生成新的待审核画像草稿，不读取聊天记忆，不覆盖现有正式画像。"/>
          <ResearchProfileStudio canAdmin={canAdmin} onApplied={()=>void load()} view="skill"/>
        </>}
        {section==="profile"&&<>
          <PageHeading kicker="TEAM RESEARCH PROFILE" title="团队研究画像" subtitle="一套共享画像：团队定位、研究主线、数据资源和方法能力，供全体成员共用。"/>
          <section className="panel cusp-profile-summary">
            <div><span className="panel-kicker">TEAM DATA FOUNDATION</span>
              <h2>团队现有数据属性：{overview?.cusp_datasets??"读取中"} 项</h2>
              <p className="small muted">CUSP Excel 数据登记单独保存在 PostgreSQL 的 cusp_datasets 表，不会自动写进研究画像 JSON，也不包含原始数据文件。可以随时查看、编辑和更新。</p>
            </div>
            <IconBtn className="btn-primary" onClick={()=>changeSection("assets")}><Database size={16}/> 查看 CUSP 数据台账 <ArrowRight size={16}/></IconBtn>
          </section>
          <div className="content-grid"><section className="panel">
            <div className="panel-header"><div><span className="panel-kicker">ACTIVE RESEARCH</span><h2>研究主线</h2></div></div>
            {!profile?<Empty icon={ShieldCheck} title="尚未建立团队研究画像" body="右侧已提供一份可编辑示例，管理员保存后，全体成员即可共享。"/>:
              <>
              {profile.team&&<div className="line-card">
                <div className="line-icon"><ShieldCheck size={20}/></div>
                <div><h3>{profile.team.name||"团队定位"}</h3>
                  <p>{profile.team.mission||"等待补充团队研究定位"}</p>
                  <small>{profile.team.priorities?.join(" · ")||""}</small>
                </div>
              </div>}
              {profile.research_lines.map(line=><div className="line-card" key={line.id}>
                <div className="line-icon"><Layers3 size={20}/></div><div><h3>{line.name}</h3><p>{line.problem}</p>
                <small>{line.method_queries.join(" · ")}</small></div></div>)}
              {(profile.datasets||[]).map((asset,i)=><div className="line-card" key={asset.name+"-"+i}>
                <div className="line-icon"><Database size={20}/></div>
                <div><h3>{asset.name}</h3><p>{asset.description||"团队共享数据资产"}</p>
                  <small>{asset.access||"权限与来源待核验"}</small></div>
              </div>)}
              </>}
          </section>
          <section className="panel">
            <div className="panel-header"><div><span className="panel-kicker">PROFILE EDITOR</span><h2>管理研究画像</h2></div></div>
            <p className="small muted">所有成员读取同一份团队画像；仅管理员能够保存修改。当前使用结构化 JSON，并保留历史版本。</p>
            <p className="small muted">当前版本：V{profileVersion} {profile?.team?.name?" · "+profile.team.name:""}</p>
            <textarea className="code-editor" spellCheck={false} readOnly={!canAdmin} value={profileText} onChange={e=>setProfileText(e.target.value)} rows={19}/>
            <div className="panel-actions"><IconBtn className="btn-primary" disabled={busy||!canAdmin} onClick={()=>void saveProfile()}>
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
          <ModelSettings canAdmin={canAdmin}/>
          <div className="settings-grid">
            {[{icon:Database,title:"科研数据库",detail:"论文、画像、选题与任务结果持久化到后端数据库",flag:"已连接数量："+(overview?.papers||0)},
              {icon:BrainCircuit,title:"Research Agent",detail:"文献发现与 AI 选题分析使用 DeepSeek；API Key 在上方模型配置中管理",flag:"密钥加密保存在服务端"},
              {icon:Workflow,title:"任务 Worker",detail:"生产环境需运行独立 worker 进程，以处理排队中的长任务",flag:"待执行："+tasks.filter(x=>x.status==="queued").length},
              {icon:ShieldCheck,title:"访问控制",detail:"浏览器访问与后端 API 分开认证；密钥仅存于服务端",flag:teamMode?"团队成员独立会话":"单用户兼容模式"}].map(x=>
              <div className="panel settings-card" key={x.title}><div className="tool-icon"><x.icon size={22}/></div>
                <h3>{x.title}</h3><p>{x.detail}</p><span>{x.flag}</span></div>)}
          </div>
          {teamMode&&<section className="panel">
            <div className="panel-header"><div><span className="panel-kicker">TEAM MEMBERS</span><h2>团队成员与权限</h2></div>
              <span className="counter">{members.length||"共享"} 位成员</span></div>
            {member?.role!=="admin"?<p className="small muted">当前身份：{member?.name||"成员"}（{member?.role||"未确认"}）。团队成员信息仅管理员可管理。</p>:<>
              <div className="evidence-list">{members.map(m=><div className="evidence" key={m.id}>
                <div><strong>{m.name} · {m.role==="admin"?"管理员":m.role==="researcher"?"研究成员":"只读成员"}</strong>
                  <span>{m.email} · {m.active?"正常":"已停用"}</span></div>
                <IconBtn disabled={busy||m.id===member.id} onClick={()=>void changeMember(m,!m.active)}>
                  {m.active?"停用":"重新启用"}
                </IconBtn>
              </div>)}</div>
              <div className="panel-actions" style={{justifyContent:"flex-start",marginTop:24}}>
                <strong>新增成员</strong>
              </div>
              <div className="feedback-grid">
                <label>姓名<input value={inviteName} onChange={e=>setInviteName(e.target.value)} placeholder="团队成员姓名"/></label>
                <label>邮箱<input type="email" value={inviteEmail} onChange={e=>setInviteEmail(e.target.value)} placeholder="name@university.edu"/></label>
              </div>
              <div className="feedback-grid" style={{marginTop:12}}>
                <label>角色<select value={inviteRole} onChange={e=>setInviteRole(e.target.value as "admin"|"researcher"|"viewer")}>
                  <option value="researcher">研究成员</option><option value="viewer">只读成员</option>
                  <option value="admin">管理员</option></select></label>
                <label>初始密码<input type="password" autoComplete="new-password" value={invitePassword}
                  onChange={e=>setInvitePassword(e.target.value)} placeholder="至少 12 字符，请通过安全渠道单独发给成员"/></label>
                <IconBtn className="btn-primary" disabled={busy||invitePassword.length<12||!inviteEmail||inviteName.length<2} onClick={()=>void inviteMember()}>
                  <Plus size={15}/> 创建成员
                </IconBtn>
              </div>
              <p className="small muted">仅在数据库中保存 Argon2 密码哈希。成员无需独立知识库；全部成员共用论文与选题。</p>
              <div className="panel-actions" style={{justifyContent:"flex-start",marginTop:24}}><strong>最近操作记录</strong></div>
              <div className="evidence-list">{audits.slice(0,12).map(a=><div className="evidence" key={a.id}>
                <div><strong>{a.action}</strong><span>{a.target} · {dateLabel(a.created_at)} · {a.note}</span></div>
              </div>)}</div>
            </>}
          </section>}
          <section className="panel"><h2>上线前配置</h2><p className="small muted">
            团队模式需要前后端同时设置 TEAM_AUTH_ENABLED=true，前端配置 BACKEND_URL 和 API_BEARER_TOKEN，
            后端配置 APP_ENV、DATABASE_URL、API_BEARER_TOKEN，并先使用 CLI 创建首位管理员。
            旧版 APP_PASSWORD 仅作为单用户兼容方案。模型密钥只放后端，公开仓库不得包含未发表资料和密钥。
          </p></section>
        </>}
      </div>
      <footer className="footer"><span>RESEARCH ATLAS · TEAM WORKBENCH V0.3</span>
        <span>Evidence before innovation claims · © Research Atlas</span></footer>
    </main>
  </div>;
}

function PageHeading({kicker,title,subtitle}:{kicker:string;title:string;subtitle:string}){
  return <div className="page-heading"><span className="panel-kicker">{kicker}</span>
    <h1>{title}</h1><p>{subtitle}</p></div>;
}
