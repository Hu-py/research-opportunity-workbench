"use client";

import Link from "next/link";
import {useCallback,useEffect,useMemo,useState} from "react";
import {usePathname} from "next/navigation";
import {
  Activity,AlertTriangle,ArrowLeft,ArrowRight,BookOpen,Check,CheckCircle2,ChevronRight,
  CircleHelp,Clock3,Database,ExternalLink,FileText,Filter,FlaskConical,GitBranch,
  GitPullRequest,History,Layers3,LockKeyhole,Plus,RefreshCw,Search,Settings2,
  ShieldCheck,SlidersHorizontal,Users,Workflow,X
} from "lucide-react";
import type {LucideIcon} from "lucide-react";
import {api} from "@/lib/api";
import {categoryTitles,designSources,groupTitles,moduleLabels,moduleScopes,referenceDocuments,workflows} from "./devstudio-reference";
import "./devstudio-v02.css";

type Member={id:string;name:string;role:"admin"|"researcher"|"viewer"};
type Session={authenticated:boolean;team:boolean;member:Member|null};
type Module={id:string;name:string;scope:string};
type Overview={modules:Module[];counts:{open_issues:number;pending_changes:number;experiments:number;indexed_documents:number};pending_review_experiment_ids?:string[];deployment_status:string;note:string};
type Issue={id:string;module_id:string;title:string;description:string;severity:string;status:string;created_at:string;created_by:string};
type Change={id:string;module_id:string;kind:string;title:string;reason:string;risk:string;status:string;created_at:string;created_by:string;issue_id:string;proposed:Record<string,unknown>};
type Document={id:string;module_id:string;title:string;category:string;authoritative_url:string;revision_ref:string;status:string;owner_id:string;created_at:string};
type Experiment={id:string;module_id:string;title:string;hypothesis:string;baseline:string;input_snapshot_ref:string;metrics:string[];change_id:string;status:string;created_at:string};
type Run={id:string;experiment_id:string;kind:string;external_url:string;code_sha:string;input_hash:string;note:string;status:string;created_at:string};
type Evaluation={id:string;run_id:string;rubric_version:string;scores:Record<string,number>;limitations:string;reviewer_id:string;created_at:string};
type Decision={id:string;change_id:string;decision:string;reason:string;reviewer_id:string;created_at:string};
type Lineage={module_id:string;issues:Issue[];changes:Change[];experiments:Experiment[];runs:Run[];decisions:Decision[];note:string};
type SourcesData={legacy_registry:{id:string;name:string;abbreviation:string;kind:string;domain:string;enabled:boolean;resolution_status:string}[];source_proposals:Change[];warning:string};
type Page="overview"|"sources"|"documents"|"experiments"|"changes"|"workflows"|"settings";
type ModalType="search"|"source"|"document"|"docRevision"|"experiment"|"run"|"evaluation"|"change"|"approval"|"issue"|"info";
type Modal={type:ModalType;id?:string;message?:string;action?:"approve"|"reject"|"request_changes"};
type Detail={kind:"source"|"document"|"change"|"module";id:string};
type Feedback="认可"|"需修改"|"待讨论";
type Task={id:string;module_id:string;title:string;note:string;kind:"issue"|"change"|"review";ref:string};
type Nav={id:Page;label:string;icon:LucideIcon;main:boolean};
const navItems:Nav[]=[
  {id:"overview",label:"研发总览",icon:Layers3,main:true},
  {id:"sources",label:"学术来源与配置",icon:BookOpen,main:true},
  {id:"documents",label:"文档中心",icon:FileText,main:true},
  {id:"experiments",label:"实验与评测",icon:FlaskConical,main:true},
  {id:"changes",label:"版本与审批",icon:GitBranch,main:true},
  {id:"workflows",label:"AI 工作流配置",icon:Workflow,main:false},
  {id:"settings",label:"团队与系统",icon:Settings2,main:false},
];
const pageInfo:Record<Page,{title:string;summary:string;eyebrow:string}>={
  overview:{title:"研发总览",summary:"先回答“平台正在做什么、为什么这样做、下一个技术决策是什么”，再看实验数字。",eyebrow:"DEVELOPMENT STUDIO / OVERVIEW"},
  sources:{title:"学术来源与配置",summary:"A 规划应用、B 城市科学、C 计算方法。每次新增、暂停或重分类都应留下原因和审批。",eyebrow:"DEVELOPMENT STUDIO / SOURCES"},
  documents:{title:"文档中心",summary:"统一索引 ChatGPT Page、GitHub 规范、文档负责人和修订历史，而非再建一个文档堆放处。",eyebrow:"DEVELOPMENT STUDIO / DOCUMENTS"},
  experiments:{title:"实验与评测",summary:"实验包含假设与固定输入；一个实验可关联多次运行，科研评审与软件测试独立记录。",eyebrow:"DEVELOPMENT STUDIO / EXPERIMENTS"},
  changes:{title:"版本与审批",summary:"把为什么修改、代码如何变化、实验提供的证据、谁批准和是否生效串成版本历史。",eyebrow:"DEVELOPMENT STUDIO / CHANGES"},
  workflows:{title:"AI 工作流配置",summary:"查看 SC01 / SC02 / SC03 的流程定义与配置要求；正式运行参数需要单独核验。",eyebrow:"DEVELOPMENT STUDIO / WORKFLOWS"},
  settings:{title:"团队与系统",summary:"权限、安全、责任人、部署事实与研发交接说明；不暴露真实密钥或个人私密资料。",eyebrow:"DEVELOPMENT STUDIO / SETTINGS"},
};
const stateNames:Record<string,string>={
  open:"待处理",submitted:"待审批",approved_pending_release:"已批准 · 待发布",
  rejected:"已拒绝",needs_revision:"退回修改",planned:"已登记 · 待执行",
  unverified:"已关联 · 未核验",indexed_draft:"草稿索引",
};
const groupKey:Record<string,string>={A:"planning_application",B:"urban_science",C:"computational_methods"};
const docsCategories=["全部","产品与需求","技术与架构","数据与接口","实验与评测","技术决策","运行与交接"];
function toLabel(s:string){return stateNames[s]||s||"未知";}
function dateLabel(s?:string){return s?s.slice(0,10):"未记录";}
function errorLabel(e:unknown){return e instanceof Error?e.message:"未知服务错误";}
function badgeTone(s:string){return s==="submitted"||s==="needs_revision"?"amber":s==="rejected"?"red":s==="approved_pending_release"?"green":s==="unverified"?"gray":"violet";}
function KV({label,value}:{label:string;value:React.ReactNode}){return <div className="dv-field"><span>{label}</span><strong>{value}</strong></div>;}
function Badge({children,tone="violet"}:{children:React.ReactNode;tone?:string}){return <span className={"dv-status dv-"+tone}>{children}</span>;}
function External({href,children}:{href:string;children:React.ReactNode}){return <a className="dv-link" href={href} target="_blank" rel="noopener noreferrer">{children} <ExternalLink size={13}/></a>;}
function PanelHeader({title,sub,action}:{title:string;sub?:string;action?:React.ReactNode}){return <div className="dv-panelhead"><h2>{title}</h2>{action||<small>{sub}</small>}</div>;}
function SectionHeader({title,sub}:{title:string;sub?:string}){return <div className="dv-sectionhead"><h2>{title}</h2><span>{sub}</span></div>;}
function Empty({children}:{children:React.ReactNode}){return <div className="dv-empty">{children}</div>;}
const emptySources:SourcesData={legacy_registry:[],source_proposals:[],warning:""};
const emptyOverview:Overview={modules:Object.keys(moduleLabels).map(id=>({id,name:moduleLabels[id],scope:moduleScopes[id]})),counts:{open_issues:0,pending_changes:0,experiments:0,indexed_documents:0},pending_review_experiment_ids:[],deployment_status:"not_verified",note:""};

export default function DevelopmentStudioV02(){
  const pathname=usePathname();
  const part=pathname.split("/")[2];
  const page:Page=navItems.some(x=>x.id===part)?part as Page:"overview";
  const [session,setSession]=useState<Session|null>(null);
  const [overview,setOverview]=useState<Overview>(emptyOverview);
  const [changes,setChanges]=useState<Change[]>([]);
  const [issues,setIssues]=useState<Issue[]>([]);
  const [experiments,setExperiments]=useState<Experiment[]>([]);
  const [documents,setDocuments]=useState<Document[]>([]);
  const [sources,setSources]=useState<SourcesData>(emptySources);
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [overviewFilter,setOverviewFilter]=useState<"all"|"approval"|"review"|"issues">("all");
  const [sourceGroup,setSourceGroup]=useState("all");
  const [sourceKind,setSourceKind]=useState("all");
  const [sourceSearch,setSourceSearch]=useState("");
  const [docCategory,setDocCategory]=useState("全部");
  const [docSearch,setDocSearch]=useState("");
  const [experimentSearch,setExperimentSearch]=useState("");
  const [changeSearch,setChangeSearch]=useState("");
  const [changeTab,setChangeTab]=useState<"requests"|"approvals"|"evolution">("requests");
  const [experimentTab,setExperimentTab]=useState<"design"|"runs"|"metrics"|"lineage">("design");
  const [selectedExperiment,setSelectedExperiment]=useState<string>("");
  const [runRows,setRunRows]=useState<Run[]>([]);
  const [evaluations,setEvaluations]=useState<Record<string,Evaluation[]>>({});
  const [selectedWorkflow,setSelectedWorkflow]=useState("SC01");
  const [lineage,setLineage]=useState<Lineage|null>(null);
  const [lineageModule,setLineageModule]=useState("DISCOVERY");
  const [detail,setDetail]=useState<Detail|null>(null);
  const [detailTab,setDetailTab]=useState("");
  const [modal,setModal]=useState<Modal|null>(null);
  const [form,setForm]=useState<Record<string,string>>({});
  const [reviewOpen,setReviewOpen]=useState(false);
  const [commandQuery,setCommandQuery]=useState("");
  const [pageFeedback,setPageFeedback]=useState<Record<string,{status:Feedback;note:string}>>({});
  const [feedbackStatus,setFeedbackStatus]=useState<Feedback>("待讨论");
  const [feedbackNote,setFeedbackNote]=useState("");

  const canWrite=session?.member?.role==="researcher"||session?.member?.role==="admin";
  const canApprove=session?.member?.role==="admin";
  const actorId=session?.member?.id;

  const refresh=useCallback(async()=>{
    setLoading(true);setError("");
    try{
      const result=await Promise.all([
        api<Overview>("devstudio/overview"),
        api<{items:Change[]}>("devstudio/changes"),
        api<{items:Issue[]}>("devstudio/issues"),
        api<{items:Experiment[]}>("devstudio/experiments"),
        api<{items:Document[]}>("devstudio/documents"),
        api<SourcesData>("devstudio/sources"),
      ]);
      setOverview(result[0]);setChanges(result[1].items);setIssues(result[2].items);
      setExperiments(result[3].items);setDocuments(result[4].items);setSources(result[5]);
    }catch(e){setError(errorLabel(e));}
    finally{setLoading(false);}
  },[]);
  useEffect(()=>{
    const onKey=(event:KeyboardEvent)=>{
      if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==="k"){
        event.preventDefault();setCommandQuery("");setModal({type:"search"});
      }
      if(event.key==="Escape"){setModal(null);setDetail(null);setReviewOpen(false);}
    };
    window.addEventListener("keydown",onKey);return()=>window.removeEventListener("keydown",onKey);
  },[]);
  useEffect(()=>{
    fetch("/api/session",{cache:"no-store"}).then(r=>r.json()).then((x:Session)=>setSession(x))
      .catch(()=>setSession({authenticated:false,team:false,member:null}));
  },[]);
  useEffect(()=>{if(session?.authenticated&&session.team)void refresh();else if(session)setLoading(false);},[session?.authenticated,session?.team,refresh]);
  useEffect(()=>{
    if(page!=="changes"||!session?.authenticated)return;
    const target=new URLSearchParams(window.location.search).get("module");
    if(target&&moduleLabels[target]){setLineageModule(target);void readLineage(target);}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[page,session?.authenticated]);

  const pending=changes.filter(x=>x.status==="submitted");
  const pendingReviewIds=overview.pending_review_experiment_ids||[];
  const pendingReview=experiments.filter(x=>pendingReviewIds.includes(x.id));
  const openIssues=issues.filter(x=>x.status==="open");
  const allModuleIds=overview.modules.map(x=>x.id);
  const filteredIds=overviewFilter==="approval"?pending.map(x=>x.module_id):
    overviewFilter==="review"?pendingReview.map(x=>x.module_id):
    overviewFilter==="issues"?openIssues.map(x=>x.module_id):allModuleIds;
  const visibleModules=overview.modules.filter(x=>filteredIds.includes(x.id));
  const tasks:Task[]=[
    ...pending.map(x=>({id:x.id,module_id:x.module_id,title:x.title,note:x.reason,kind:"change" as const,ref:x.id})),
    ...pendingReview.map(x=>({id:x.id,module_id:x.module_id,title:x.title,note:"已绑定运行，仍需登记科研评审与结果限制。",kind:"review" as const,ref:x.id})),
    ...openIssues.map(x=>({id:x.id,module_id:x.module_id,title:x.title,note:x.description,kind:"issue" as const,ref:x.id})),
  ];
  const shownTasks=overviewFilter==="approval"?tasks.filter(x=>x.kind==="change"):
    overviewFilter==="review"?tasks.filter(x=>x.kind==="review"):
    overviewFilter==="issues"?tasks.filter(x=>x.kind==="issue"):tasks.slice(0,6);
  const kpis=[
    {id:"all" as const,title:"研发能力模块",n:overview.modules.length,desc:"明确的模块分类",icon:Layers3},
    {id:"approval" as const,title:"待审批变更",n:pending.length,desc:"等待独立审核",icon:Clock3},
    {id:"review" as const,title:"待复核实验",n:pendingReview.length,desc:"有运行、尚无评审",icon:FlaskConical},
    {id:"issues" as const,title:"待处理技术问题",n:openIssues.length,desc:"基于实际问题台账",icon:AlertTriangle},
  ];
  const activeKpi=kpis.find(x=>x.id===overviewFilter)||kpis[0];

  const sourceReferences=designSources.filter(x=>
    (sourceGroup==="all"||x.group===sourceGroup)
    &&(sourceKind==="all"||x.kind===sourceKind)
    &&(x.name+" "+x.short+" "+x.reason+" "+x.channel).toLowerCase().includes(sourceSearch.toLowerCase())
  );
  const sourceProposals=sources.source_proposals.filter(x=>
    (sourceGroup==="all"||Array.isArray(x.proposed?.source_groups)&&x.proposed.source_groups.includes(groupKey[sourceGroup]))
    &&(x.title+" "+x.reason).toLowerCase().includes(sourceSearch.toLowerCase())
  );
  const docRows=documents.filter(x=>
    (docCategory==="全部"||categoryTitles[x.category]===docCategory)
    &&(x.title+" "+x.module_id+" "+x.category).toLowerCase().includes(docSearch.toLowerCase())
  );
  const referenceDocs=referenceDocuments.filter(x=>
    !documents.some(d=>d.authoritative_url===x.url)
    &&(docCategory==="全部"||categoryTitles[x.category]===docCategory)
    &&(x.title+" "+x.module_id).toLowerCase().includes(docSearch.toLowerCase())
  );
  const expRows=experiments.filter(x=>
    (x.title+" "+x.module_id+" "+x.hypothesis).toLowerCase().includes(experimentSearch.toLowerCase())
  );
  const changeRows=changes.filter(x=>
    (changeTab!=="approvals"||x.status==="submitted"&&x.created_by!==actorId&&canApprove)
    &&(x.title+" "+x.reason+" "+x.module_id).toLowerCase().includes(changeSearch.toLowerCase())
  );
  const activeExperiment=experiments.find(x=>x.id===selectedExperiment)||experiments[0];
  const searchItems=[
    ...Object.entries(moduleLabels).map(([id,title])=>({id,kind:"module",title,sub:"研发模块"})),
    ...designSources.map(x=>({id:x.id,kind:"source",title:x.name,sub:"学术关注来源 · 参考"})),
    ...documents.map(x=>({id:x.id,kind:"document",title:x.title,sub:"已登记文档"})),
    ...experiments.map(x=>({id:x.id,kind:"experiment",title:x.title,sub:"实验"})),
    ...changes.map(x=>({id:x.id,kind:"change",title:x.title,sub:"变更审批"}))
  ].filter(x=>!commandQuery.trim()||(
    x.title+" "+x.sub+" "+x.id
  ).toLowerCase().includes(commandQuery.toLowerCase())).slice(0,25);

  function openModal(type:ModalType,id?:string,message?:string,action?:Modal["action"],preset:Record<string,string>={}){
    setForm(preset);setModal({type,id,message,action});setDetail(null);setError("");
  }
  function setValue(name:string,value:string){setForm(prev=>({...prev,[name]:value}));}
  function closePopups(){setModal(null);setDetail(null);}
  async function request<T>(path:string,payload:unknown):Promise<T>{
    return api<T>(path,{method:"POST",body:JSON.stringify(payload)});
  }
  async function execute(fn:()=>Promise<unknown>,done:string){
    setBusy(true);setError("");
    try{await fn();setModal(null);setNotice(done);await refresh();}
    catch(e){setError(errorLabel(e));}
    finally{setBusy(false);}
  }
  async function loadExperimentRuns(id:string){
    setSelectedExperiment(id);setExperimentTab("design");setRunRows([]);setEvaluations({});
    try{
      const response=await api<{items:Run[]}>("devstudio/experiments/"+id+"/runs");
      setRunRows(response.items);
    }catch(e){setError(errorLabel(e));}
  }
  async function loadEvaluations(id:string){
    try{
      const response=await api<{items:Evaluation[]}>("devstudio/runs/"+id+"/evaluations");
      setEvaluations(prev=>({...prev,[id]:response.items}));
    }catch(e){setError(errorLabel(e));}
  }
  async function readLineage(moduleId:string){
    setLineageModule(moduleId);setLineage(null);
    try{setLineage(await api<Lineage>("devstudio/lineage/"+moduleId));}
    catch(e){setError(errorLabel(e));}
  }
  function openDetail(kind:Detail["kind"],id:string){
    setDetail({kind,id});setDetailTab(kind==="source"?"基本资料":kind==="document"?"基本信息":"为什么修改");
  }
  function openSearchResult(kind:string,id:string){
    setModal(null);setCommandQuery("");
    if(kind==="module")window.location.assign("/devstudio/changes?module="+encodeURIComponent(id));
    if(kind==="source")window.location.assign("/devstudio/sources?source="+encodeURIComponent(id));
    if(kind==="document")window.location.assign("/devstudio/documents?doc="+encodeURIComponent(id));
    if(kind==="experiment")window.location.assign("/devstudio/experiments?selected="+encodeURIComponent(id));
    if(kind==="change")window.location.assign("/devstudio/changes?change="+encodeURIComponent(id));
  }
  function taskAction(t:Task){
    if(t.kind==="review"){window.location.assign("/devstudio/experiments?selected="+encodeURIComponent(t.ref));return;}
    if(t.kind==="change"){window.location.assign("/devstudio/changes?change="+encodeURIComponent(t.ref));return;}
    window.location.assign("/devstudio/changes?module="+encodeURIComponent(t.module_id));
  }
  useEffect(()=>{
    if(page==="sources"){
      const target=new URLSearchParams(window.location.search).get("source");
      if(target&&designSources.some(x=>x.id===target))openDetail("source",target);
    }
    if(page==="documents"){
      const target=new URLSearchParams(window.location.search).get("doc");
      if(target&&documents.some(x=>x.id===target))openDetail("document",target);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[page,documents.length]);
  useEffect(()=>{
    if(page!=="experiments"||!experiments.length)return;
    const target=new URLSearchParams(window.location.search).get("selected");
    if(target&&experiments.some(x=>x.id===target))void loadExperimentRuns(target);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[page,experiments.length]);
  useEffect(()=>{
    if(page!=="changes"||!changes.length)return;
    const target=new URLSearchParams(window.location.search).get("change");
    if(target&&changes.some(x=>x.id===target))openDetail("change",target);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[page,changes.length]);

  async function submitModal(){
    if(!modal)return;
    const v=(key:string)=>String(form[key]||"").trim();
    if(modal.type==="source"){
      await execute(()=>request("devstudio/changes",{module_id:"DISCOVERY",kind:"source",
        title:v("operation")+" · "+v("name"),reason:v("reason"),
        proposed:{operation:v("operation")||"add",name:v("name"),source_groups:[v("group")||"urban_science"],official_url:v("url")||""}
      }),"来源变更已提交待审批，未影响正式采集任务。");
    }else if(modal.type==="document"){
      await execute(()=>request("devstudio/documents",{module_id:v("module")||"PLATFORM",
        title:v("title"),category:v("category")||"architecture",authoritative_url:v("url"),revision_ref:v("revision")}),
        "文档索引已登记；Page/GitHub 原件未被修改。");
    }else if(modal.type==="docRevision"){
      const doc=documents.find(x=>x.id===modal.id);
      if(!doc)return;
      await execute(()=>request("devstudio/changes",{module_id:doc.module_id,kind:"document",
        title:"修订文档 · "+doc.title,reason:v("reason"),proposed:{document_id:doc.id,authoritative_url:doc.authoritative_url}
      }),"文档修订申请已提交，待审查原件。");
    }else if(modal.type==="experiment"){
      await execute(()=>request("devstudio/experiments",{module_id:v("module")||"DISCOVERY",
        title:v("title"),hypothesis:v("hypothesis"),baseline:v("baseline"),
        input_snapshot_ref:v("snapshot"),change_id:v("change")||""}),
        "实验设计已登记，可关联实际运行。");
    }else if(modal.type==="run"){
      const expId=modal.id||selectedExperiment;
      await execute(async()=>{
        await request("devstudio/experiments/"+expId+"/runs",{
          kind:"github_actions",external_url:v("url"),code_sha:v("sha"),note:v("note")
        });
        await loadExperimentRuns(expId);
      },"GitHub Run 已关联；未核验外部运行状态。");
    }else if(modal.type==="evaluation"){
      const runId=modal.id;if(!runId)return;
      await execute(async()=>{
        await request("devstudio/runs/"+runId+"/evaluations",{
          rubric_version:"manual-research-review-v1",scores:{research_quality:Number(v("score"))},
          limitations:v("reason")
        });
        await loadEvaluations(runId);
      },"人工评分已保存，不等于软件或科研自动验收通过。");
    }else if(modal.type==="change"){
      const kind=v("kind")||"code";
      await execute(()=>request("devstudio/changes",{module_id:v("module")||"DISCOVERY",
        kind,title:v("title"),reason:v("reason"),proposed:{scope:v("proposal")||"Needs implementation and independent review"}
      }),"研发变更已提交，等待评审。");
    }else if(modal.type==="issue"){
      await execute(()=>request("devstudio/issues",{module_id:v("module")||"DISCOVERY",
        title:v("title"),description:v("reason"),severity:v("severity")||"medium"
      }),"研发问题已登记。");
    }else if(modal.type==="approval"){
      if(!modal.id||!modal.action)return;
      await execute(()=>request("devstudio/changes/"+modal.id+"/decisions",{
        decision:modal.action,reason:v("reason")
      }),"已记录审核决定；批准不等于正式发布或生产生效。");
    }
  }

  function feedbackSave(){
    setPageFeedback(prev=>({...prev,[page]:{status:feedbackStatus,note:feedbackNote.trim()}}));
    setNotice("当前页面反馈已保留在本次浏览器会话中，可导出评审意见。");
  }
  function feedbackExport(){
    const text=navItems.map(n=>{
      const entry=pageFeedback[n.id];return "## "+n.label+"\n状态："+(entry?.status||"待讨论")+"\n意见："+(entry?.note||"无")+"\n";
    }).join("\n");
    const blob=new Blob(["# Research Atlas Development Studio UI 评审\n\n"+text],{type:"text/markdown;charset=utf-8"});
    const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download="Development_Studio_UI_Review.md";a.click();URL.revokeObjectURL(url);
  }

  const titles=pageInfo[page];
  const sectionButton=(text:string,action:()=>void,primary=false)=><button type="button" className={"dv-btn"+(primary?" dv-primary":"")} onClick={action}>{text}</button>;
  return <div className="dv-app">
    <aside className="dv-sidebar">
      <Link className="dv-brand" href="/"><div className="dv-brandmark">✦</div>
        <div><strong>Research Atlas</strong><small>DEVELOPMENT STUDIO</small></div>
      </Link>
      <div className="dv-sidescroll">
        <div className="dv-sidelabel">研发工作台</div>
        <nav aria-label="研发工作台主导航">{navItems.filter(x=>x.main).map(n=><Link key={n.id}
          className={"dv-navitem"+(page===n.id?" active":"")} aria-current={page===n.id?"page":undefined}
          href={n.id==="overview"?"/devstudio":"/devstudio/"+n.id}><n.icon size={18}/><span>{n.label}</span></Link>)}</nav>
        <div className="dv-sidelabel">配置与运维</div>
        <nav aria-label="配置与运维">{navItems.filter(x=>!x.main).map(n=><Link key={n.id}
          className={"dv-navitem"+(page===n.id?" active":"")} aria-current={page===n.id?"page":undefined}
          href={"/devstudio/"+n.id}><n.icon size={18}/><span>{n.label}</span></Link>)}</nav>
      </div>
      <div className="dv-sidebarbottom">
        <div className="dv-minipanel"><span className="dv-onlinedot"/> 开发分支 / P0 <small>所有数据读取与操作以真实后端为准；审批不会自动发布到生产。</small></div>
        <Link className="dv-back" href="/"><ArrowLeft size={13}/> 返回 Research Atlas 工作台</Link>
      </div>
    </aside>
    <main className="dv-main">
      <header className="dv-topbar">
        <div className="dv-crumb"><span>Research Atlas</span><ChevronRight size={14}/><strong>{titles.title}</strong></div>
        <div className="dv-topactions">
          <button className="dv-topsearch" type="button" onClick={()=>{setCommandQuery("");openModal("search");}}><Search size={14}/> 搜索模块、期刊、文档 <kbd>⌘ K</kbd></button>
          <span className="dv-headpill">P0 · 待部署</span>
          <button type="button" title="刷新真实数据" aria-label="刷新真实数据" className="dv-topicon" onClick={()=>void refresh()}><RefreshCw size={16}/></button>
          <span className="dv-avatar" title={session?.member?.role||"未登录"}>{session?.member?.name?.slice(0,1)||"研"}</span>
        </div>
      </header>
      <div className="dv-wrap">
        <div className="dv-notice"><span><strong>实际研发版本</strong> · 界面依据已确认的 HTML V0.2；示例来源和参考文档均明确标注，后台数据来自当前开发库。GitHub PR #58 尚未合并或部署。</span>
          <button type="button" onClick={()=>{setReviewOpen(true);setFeedbackStatus(pageFeedback[page]?.status||"待讨论");setFeedbackNote(pageFeedback[page]?.note||"");}}>逐页反馈 ↗</button>
        </div>
        {!session&&<div className="dv-panel"><Empty>正在检查团队账号登录状态…</Empty></div>}
        {session&&(!session.authenticated||!session.team)&&<div className="dv-panel dv-lockpanel">
          <LockKeyhole size={34}/><h2>需要团队账号登录</h2><p>正式研发管理台包含来源变更、审查与实验记录。请返回工作台登录，并确认团队认证已启用。</p>
          <Link href="/" className="dv-btn dv-primary">返回科研工作台 <ArrowRight size={14}/></Link>
        </div>}
        {session?.authenticated&&session.team&&<>
          <div className="dv-pagehead">
            <div><span className="dv-eyebrow">{titles.eyebrow}</span><h1>{titles.title}</h1><p>{titles.summary}</p></div>
            <div className="dv-headactions">
              {page==="overview"&&<>{sectionButton("＋ 提交变更",()=>openModal("change",undefined,undefined,undefined,{module:"DISCOVERY",kind:"code"}),true)}<Link className="dv-btn" href="/devstudio/changes?module=DISCOVERY">查看演化链</Link></>}
              {page==="sources"&&<>{canWrite&&sectionButton("＋ 提出来源变更",()=>openModal("source",undefined,undefined,undefined,{operation:"add",group:"urban_science"}),true)}{sectionButton("配置版本说明",()=>openModal("info",undefined,"当前只登记候选变更和审批。新 A/B/C 目录的正式版本化发布尚未接入生产采集器。"))}</>}
              {page==="documents"&&<>{canWrite&&sectionButton("＋ 登记文档",()=>openModal("document",undefined,undefined,undefined,{module:"PLATFORM",category:"architecture"}),true)}{sectionButton("文档修订规则",()=>openModal("info",undefined,"Page/GitHub 原文仍为权威记录。文档修订申请进入独立审批；批准不会自动改写原件。"))}</>}
              {page==="experiments"&&<>{canWrite&&sectionButton("＋ 新建实验",()=>openModal("experiment",undefined,undefined,undefined,{module:"DISCOVERY"}),true)}{sectionButton("实验分类",()=>openModal("info",undefined,"三个维度独立分类：科研能力模块 × 实验目标 × 使用场景。每次 Run 保留自己的代码版本与输入快照。"))}</>}
              {page==="changes"&&<>{canWrite&&sectionButton("＋ 创建变更",()=>openModal("change",undefined,undefined,undefined,{module:"DISCOVERY",kind:"code"}),true)}{sectionButton("审批规则",()=>openModal("info",undefined,"研究成员提交；独立管理员审查。批准仅产生待发布状态，不能直接更改采集、模型或部署。"))}</>}
              {page==="workflows"&&<>{sectionButton("配置差异预览",()=>openModal("info",undefined,"工作流配置 Diff 和自动发布属于下一阶段 P1。本页只展示规格中定义的流程和未核验的运行状态。"))}{canWrite&&sectionButton("提出流程变更",()=>openModal("change",undefined,undefined,undefined,{module:"PLATFORM",kind:"workflow",title:"工作流配置调整"}),true)}</>}
              {page==="settings"&&sectionButton("权限规则",()=>openModal("info",undefined,"当前真实后端复用团队账号：viewer 只读、researcher 可提交、admin 可批准他人的申请。更细粒度角色规划在 P1。"))}
            </div>
          </div>
          {error&&<div className="dv-alert dv-error" role="alert"><AlertTriangle size={15}/><span>{error}</span><button onClick={()=>setError("")}>×</button></div>}
          {notice&&<div className="dv-alert dv-success" role="status"><CheckCircle2 size={15}/><span>{notice}</span><button onClick={()=>setNotice("")}>×</button></div>}
          {loading?<div className="dv-panel"><Empty>正在读取真实研发台账…</Empty></div>:<>
            {page==="overview"&&<>
              <div className="dv-kpigrid">
                {kpis.map((k,i)=><button key={k.id} type="button"
                  className={"dv-panel dv-kpi dv-kpifilter"+(overviewFilter===k.id?" is-active":"")}
                  aria-pressed={overviewFilter===k.id} onClick={()=>setOverviewFilter(prev=>prev===k.id?"all":k.id)}>
                  <div><span className="dv-kpiname">{k.title}</span><strong className="dv-kpinum">{k.n}</strong><small>{k.desc}</small></div>
                  <span className={"dv-kpiicon dv-ki"+i}><k.icon size={20}/></span>
                </button>)}
              </div>
              <div className="dv-filterstate" role="status"><div><Filter size={14}/><strong>{overviewFilter==="all"?"当前显示：全部研发模块":"筛选："+activeKpi.title}</strong><span>· 下方显示 {visibleModules.length} 个关联模块、{shownTasks.length} 条待办/记录</span></div>
                {overviewFilter==="all"?<small>点击上方卡片可筛选下方列表</small>:
                  <button type="button" className="dv-btn dv-tiny" onClick={()=>setOverviewFilter("all")}>清除筛选 ×</button>}
              </div>
              <div className="dv-twocol">
                <div className="dv-panel"><PanelHeader title="科研 AI 能力与研发版本" sub={"已筛选 "+visibleModules.length+" / "+overview.modules.length+" 个模块 · "+activeKpi.title}/>
                  <div className="dv-tablewrap"><table className="dv-table"><thead><tr><th>能力模块</th><th>研发状态</th><th>版本线索</th><th>问题与下一步</th></tr></thead>
                    <tbody>{visibleModules.map(m=>{
                      const xPending=pending.filter(x=>x.module_id===m.id);
                      const xIssues=openIssues.filter(x=>x.module_id===m.id);
                      const xExp=experiments.filter(x=>x.module_id===m.id);
                      const desc=xIssues[0]?.title||xPending[0]?.title||"尚未登记待解决的问题";
                      const stage=xPending.length?"有待审批变更":xIssues.length?"有待处理问题":xExp.length?"已登记实验":"状态待核验";
                      return <tr key={m.id} className="dv-clickrow" onClick={()=>openDetail("module",m.id)}>
                        <td><b>{moduleLabels[m.id]||m.name}</b><small>{m.id}</small></td>
                        <td><Badge tone={xPending.length?"violet":xIssues.length?"amber":"gray"}>{stage}</Badge></td>
                        <td>{m.id==="DISCOVERY"?<External href="https://github.com/Hu-py/research-opportunity-workbench/pull/57">PR #57 草稿</External>:m.id==="PLATFORM"?<External href="https://github.com/Hu-py/research-opportunity-workbench/pull/58">PR #58 草稿</External>:<span className="dv-muted">未登记正式版本</span>}</td>
                        <td>{desc} →</td>
                      </tr>;
                    })}</tbody></table></div>
                  {!visibleModules.length&&<Empty>本筛选下暂无关联模块。</Empty>}
                </div>
                <div className="dv-panel"><PanelHeader title={overviewFilter==="all"?"我的待办与风险":activeKpi.title+" · 对应记录"} sub={shownTasks.length+" 项 · 点击查看详情"}/>
                  <div className="dv-tasklist">{shownTasks.map((t,i)=><button type="button" key={t.id} className="dv-task" onClick={()=>taskAction(t)}>
                    <span className="dv-idx">{String(i+1).padStart(2,"0")}</span><span><strong>{t.title}</strong><small>{t.note}</small></span>
                  </button>)}{!shownTasks.length&&<Empty>当前筛选没有待处理记录。</Empty>}</div>
                  <div className="dv-callout"><strong>状态提醒：</strong> CI 通过不代表产品已上线；OpenAlex 采集成功也不代表科研结果已通过评审。</div>
                </div>
              </div>
              <SectionHeader title="最近的研发演化" sub="以实际登记关系为准，不从时间相邻推断原因"/>
              <div className="dv-twocol">
                <div className="dv-panel"><PanelHeader title="模块变化与技术决策" sub="可追溯记录"/>
                  <div className="dv-timeline">{changes.slice(0,4).map(x=><div className="dv-timeitem" key={x.id}><strong>{x.title}</strong><Badge tone={badgeTone(x.status)}>{toLabel(x.status)}</Badge><p>{x.reason}</p><small>{dateLabel(x.created_at)} · {x.module_id}</small></div>)}
                    {!changes.length&&<Empty>尚无已登记变更。可以先从发现的问题创建 Change Record。</Empty>}</div>
                  <Link className="dv-btn" href="/devstudio/changes?module=DISCOVERY">打开版本演化链 →</Link>
                </div>
                <div className="dv-panel"><PanelHeader title="关联证据与开发进度" sub="GitHub 真实链接"/>
                  <div className="dv-refcard"><span className="dv-eyebrow">AI WORKFLOW · DRAFT PR</span><h3>三来源科研工作流 #57</h3><p>学术来源、采集器与对照实验，仍需完成科研采集评估及合并验收。</p><External href="https://github.com/Hu-py/research-opportunity-workbench/pull/57">查看 PR #57</External></div>
                  <div className="dv-refcard"><span className="dv-eyebrow">PLATFORM · DRAFT PR</span><h3>Development Studio #58</h3><p>本前端据批准的 V0.2 HTML 实现；正式合并、部署和实测仍需检查。</p><External href="https://github.com/Hu-py/research-opportunity-workbench/pull/58">查看 PR #58</External></div>
                </div>
              </div>
            </>}
            {page==="sources"&&<>
              <div className="dv-kpigrid">
                {[[designSources.length,"设计参考来源","非已生效目录",BookOpen],[3,"A/B/C 来源类别","支持多组归属",Layers3],[2,"已知实测问题","SCS / JMLR",AlertTriangle],["先审后用","审批原则","不自动发布",ShieldCheck]].map(([n,title,desc,Icon],i)=>{
                  const I=Icon as LucideIcon;return <div className="dv-panel dv-kpi" key={String(title)}><div><span className="dv-kpiname">{String(title)}</span><strong className="dv-kpinum">{n as React.ReactNode}</strong><small>{String(desc)}</small></div><span className={"dv-kpiicon dv-ki"+i}><I size={20}/></span></div>;
                })}
              </div>
              <div className="dv-panel">
                <div className="dv-filterbar">
                  <div className="dv-filterleft">{["all","A","B","C"].map(g=><button type="button" key={g} className={"dv-btn dv-tiny"+(sourceGroup===g?" dv-primary":"")} onClick={()=>setSourceGroup(g)}>{g==="all"?"全部来源":groupTitles[g]}</button>)}</div>
                  <div className="dv-filterright"><label className="dv-search"><Search size={14}/><input value={sourceSearch} placeholder="搜索期刊、会议或关注理由" onChange={e=>setSourceSearch(e.target.value)}/></label>
                    <select className="dv-select" aria-label="来源类型" value={sourceKind} onChange={e=>setSourceKind(e.target.value)}><option value="all">全部类型</option><option>期刊</option><option>会议</option></select>
                  </div>
                </div>
                <div className="dv-tablewrap"><table className="dv-table"><thead><tr><th>关注来源</th><th>分类</th><th>优先级</th><th>发现渠道</th><th>来源状态</th><th>维护人</th></tr></thead><tbody>
                  {sourceReferences.map(x=><tr className="dv-clickrow" key={x.id} onClick={()=>openDetail("source",x.id)}><td><b>{x.name}</b><small>{x.short} · {x.kind} · 设计参考</small></td><td><span className="dv-chip">{x.group}</span></td><td>{x.priority}</td><td>{x.channel}</td><td><Badge tone={x.status.includes("问题")||x.status.includes("归属")?"amber":"gray"}>{x.status}</Badge></td><td>待指定</td></tr>)}
                </tbody></table></div>
                {!sourceReferences.length&&<Empty>没有匹配的参考期刊或会议。</Empty>}
                <div className="dv-resultfoot"><span>以上 {sourceReferences.length} 条为 V0.2 设计参考，不是生产来源配置。真实审批记录见下方。</span></div>
              </div>
              <SectionHeader title="学术来源维护与审批" sub="提交后不自动生效 · 来自实际数据库"/>
              <div className="dv-panel"><PanelHeader title="已登记来源变更" sub={sourceProposals.length+" 条当前筛选记录"}/>
                <div className="dv-tablewrap"><table className="dv-table"><thead><tr><th>申请内容</th><th>来源分类</th><th>当前状态</th><th>提出理由</th></tr></thead><tbody>
                  {sourceProposals.map(x=><tr className="dv-clickrow" key={x.id} onClick={()=>openDetail("change",x.id)}><td><b>{x.title}</b><small>{x.id}</small></td><td>{Array.isArray(x.proposed?.source_groups)?x.proposed.source_groups.map(g=>groupTitles[String(g)]||String(g)).join(" / "):"未记录"}</td><td><Badge tone={badgeTone(x.status)}>{toLabel(x.status)}</Badge></td><td>{x.reason}</td></tr>)}
                </tbody></table></div>{!sourceProposals.length&&<Empty>尚无当前分类下的来源变更申请。</Empty>}
              </div>
              <div className="dv-grid3">
                {["提出变更","审核身份与差异","审批与受控生效"].map((x,i)=><div key={x} className="dv-panel"><span className="dv-eyebrow">STEP 0{i+1}</span><h3>{x}</h3><p className="dv-muted">{["填写来源名称、A/B/C 归属和研究关注理由。","校验官方网页、来源 ID 和重复收录风险。","批准变更并形成版本；正式上线由后续发布控制。"][i]}</p></div>)}
              </div>
              <div className="dv-callout"><strong>旧来源表：</strong>现有数据库中另有 {sources.legacy_registry.length} 条 Radar 目录记录，其 direct/method 语义不等同 A/B/C，不能自动分类。</div>
            </>}
            {page==="documents"&&<div className="dv-threecol">
              <div className="dv-panel"><PanelHeader title="文档类别"/>{docsCategories.map(cat=><button type="button" key={cat} className={"dv-doccat"+(docCategory===cat?" active":"")} onClick={()=>setDocCategory(cat)}>
                <FileText size={14}/>{cat}<span>{cat==="全部"?documents.length+referenceDocs.length:documents.filter(d=>categoryTitles[d.category]===cat).length+referenceDocuments.filter(d=>categoryTitles[d.category]===cat&&!documents.some(x=>x.authoritative_url===d.url)).length}</span>
              </button>)}<hr/><p className="dv-muted">原文仍存放在 Page 或 GitHub，后台维护文档索引与审核责任。</p></div>
              <div className="dv-panel"><div className="dv-filterbar"><label className="dv-search"><Search size={14}/><input value={docSearch} placeholder="搜索文档或模块" onChange={e=>setDocSearch(e.target.value)}/></label><span className="dv-muted">{docRows.length} 条已登记 · {referenceDocs.length} 条可导入参考</span></div>
                <div className="dv-tablewrap"><table className="dv-table"><thead><tr><th>文档标题</th><th>模块</th><th>状态</th></tr></thead><tbody>
                  {docRows.map(d=><tr className="dv-clickrow" key={d.id} onClick={()=>openDetail("document",d.id)}><td><b>{d.title}</b><small>数据库索引 · {dateLabel(d.created_at)}</small></td><td>{d.module_id}</td><td><Badge tone="violet">{toLabel(d.status)}</Badge></td></tr>)}
                  {referenceDocs.map(d=><tr key={d.id} className="dv-docsuggest"><td><b>{d.title}</b><small>{d.source} · 参考链接</small></td><td>{d.module_id}</td><td>{canWrite?<button type="button" className="dv-btn dv-tiny" onClick={()=>openModal("document",undefined,undefined,undefined,{title:d.title,module:d.module_id,category:d.category,url:d.url,revision:d.revision})}>登记索引</button>:<Badge tone="gray">待登记</Badge>}</td></tr>)}
                </tbody></table></div>
                {!docRows.length&&!referenceDocs.length&&<Empty>没有匹配的文档。</Empty>}
              </div>
              <div className="dv-panel"><PanelHeader title="文档治理提醒"/>
                <div className="dv-tasklist">
                  {[
                    ["权威原件与讨论稿区分","Page 可作为设计讨论源，未经审查不能称正式执行规范。"],
                    ["维护人和替代版本","每份文档应有维护者、当前版本与被替代的历史记录。"],
                    ["文档与代码一致性","Draft PR 和已批准技术 Page 可能存在时序差异，需单独核验。"],
                  ].map((x,i)=><div className="dv-task" key={x[0]}><span className="dv-idx">{String(i+1).padStart(2,"0")}</span><span><strong>{x[0]}</strong><small>{x[1]}</small></span></div>)}
                </div><div className="dv-callout">文档正文不在后台复制出第二份。P1 才增加代码/文档自动一致性提示。</div>
              </div>
            </div>}
            {page==="experiments"&&<>
              <div className="dv-panel"><div className="dv-filterbar"><label className="dv-search"><Search size={14}/><input value={experimentSearch} onChange={e=>setExperimentSearch(e.target.value)} placeholder="按实验问题、模块搜索"/></label>
                <span className="dv-muted">能力模块 × 实验目标 × 使用场景</span></div>
                <div className="dv-tablewrap"><table className="dv-table"><thead><tr><th>实验 / 编号</th><th>所属模块</th><th>状态</th><th>基线与证据</th></tr></thead><tbody>
                  {expRows.map(x=><tr key={x.id} className="dv-clickrow" onClick={()=>void loadExperimentRuns(x.id)}><td><b>{x.title}</b><small>{x.id}</small></td><td>{x.module_id}</td><td><Badge tone="gray">{toLabel(x.status)}</Badge></td><td>{x.baseline||"未记录基线"}</td></tr>)}
                </tbody></table></div>{!expRows.length&&<Empty>尚未登记实验。已有 OpenAlex 实验报告可通过“新建实验”录入并关联真实运行。</Empty>}
              </div>
              <div className="dv-panel dv-experimentdetail">
                <PanelHeader title={activeExperiment?activeExperiment.title:"实验详情"} sub={activeExperiment?activeExperiment.id:"请选择表格中的实验"}/>
                {activeExperiment?<><div className="dv-tabs">{[
                  ["design","实验设计"],["runs","运行记录"],["metrics","指标与审查"],["lineage","演化与决策"]
                ].map(([id,label])=><button key={id} type="button" className={"dv-tab"+(experimentTab===id?" active":"")} onClick={()=>setExperimentTab(id as typeof experimentTab)}>{label}</button>)}</div>
                  {experimentTab==="design"&&<>
                    <KV label="所属能力" value={activeExperiment.module_id}/><KV label="研究假设" value={activeExperiment.hypothesis}/><KV label="对照基线" value={activeExperiment.baseline||"未登记"}/><KV label="输入快照" value={activeExperiment.input_snapshot_ref||"未冻结"}/><KV label="关联变更" value={activeExperiment.change_id||"无关联"}/>
                    <div className="dv-callout">未登记输入快照、基线或已批准评价时，不能将实验直接标为“科研质量通过”。</div>
                  </>}
                  {experimentTab==="runs"&&<>
                    {runRows.map(x=><div key={x.id} className="dv-runrow"><div><b>{x.id}</b><small>{dateLabel(x.created_at)} · {toLabel(x.status)}</small><p>{x.note}</p></div><div>{x.external_url.startsWith("https://")?<External href={x.external_url}>GitHub Run</External>:<span>{x.external_url}</span>}</div></div>)}
                    {!runRows.length&&<Empty>本实验尚无已关联运行记录。</Empty>}
                    {canWrite&&sectionButton("＋ 关联真实 GitHub Run",()=>openModal("run",activeExperiment.id),true)}
                  </>}
                  {experimentTab==="metrics"&&<>
                    {runRows.map(x=><div key={x.id} className="dv-runrow"><div><b>运行 {x.id.slice(0,14)}</b><small>{toLabel(x.status)} · 科研评审单独登记</small></div><div><button type="button" className="dv-btn dv-tiny" onClick={()=>void loadEvaluations(x.id)}>读取评分</button> {canWrite&&<button type="button" className="dv-btn dv-tiny dv-primary" onClick={()=>openModal("evaluation",x.id)}>追加评审</button>}</div>
                      {(evaluations[x.id]||[]).map(ev=><div key={ev.id} className="dv-fullrow"><Badge tone="violet">人工评分 {ev.scores.research_quality??"未填"} / 5</Badge><small>{ev.limitations||"未填写限制"} · {dateLabel(ev.created_at)}</small></div>)}
                    </div>)}{!runRows.length&&<Empty>请先关联真实运行，再进行人工科研审查。</Empty>}
                  </>}
                  {experimentTab==="lineage"&&<div className="dv-callout"><b>关联变更：</b>{activeExperiment.change_id||"未建立显式 Change 关联"}。需要回溯代码、参数和来源版本时应以固定哈希与真实运行记录为准。</div>}
                </>:<><Empty>请选择表格中的实验或登记新的实验。</Empty><div className="dv-callout">历史参考：<External href="https://github.com/Hu-py/research-opportunity-workbench/actions/runs/43552802805">2026-11-14 OpenAlex 真实采集 Run</External>。它尚未自动写入本管理台数据库。</div></>}
              </div>
            </>}
            {page==="changes"&&<>
              <div className="dv-panel"><div className="dv-tabs">{[
                ["requests","变更请求"],["approvals","我的审批"],["evolution","版本演化"]
              ].map(([id,label])=><button type="button" className={"dv-tab"+(changeTab===id?" active":"")} key={id} onClick={()=>{setChangeTab(id as typeof changeTab);if(id==="evolution")void readLineage(lineageModule);}}>{label}{id==="approvals"?" · "+pending.filter(x=>x.created_by!==actorId&&canApprove).length:""}</button>)}</div>
                {changeTab==="evolution"?<>
                  <div className="dv-filterbar"><div><strong>{moduleLabels[lineageModule]}</strong><p className="dv-muted">根据明确 ID 关联展示问题 → 修改 → 实验 → 决策。</p></div>
                    <select aria-label="选择演化模块" className="dv-select" value={lineageModule} onChange={e=>void readLineage(e.target.value)}>{Object.entries(moduleLabels).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select>
                  </div>
                  <div className="dv-twocol">
                    <div className="dv-timeline">
                      {lineage&&[
                        ...lineage.issues.map(x=>({id:x.id,kind:"问题",title:x.title,summary:x.description,date:x.created_at})),
                        ...lineage.changes.map(x=>({id:x.id,kind:"变更",title:x.title,summary:x.reason,date:x.created_at})),
                        ...lineage.experiments.map(x=>({id:x.id,kind:"实验",title:x.title,summary:x.hypothesis,date:x.created_at})),
                        ...lineage.decisions.map(x=>({id:x.id,kind:"审批",title:x.decision,summary:x.reason,date:x.created_at})),
                      ].sort((a,b)=>a.date.localeCompare(b.date)).map(x=><div className="dv-timeitem" key={x.id}><strong>{x.title}</strong><Badge tone="gray">{x.kind}</Badge><p>{x.summary}</p><small>{dateLabel(x.date)} · {x.id}</small></div>)}
                      {!lineage||!(lineage.issues.length+lineage.changes.length+lineage.experiments.length+lineage.decisions.length)?<Empty>当前模块尚无完整演化记录，可先从实际问题与变更申请建立关系。</Empty>:null}
                    </div>
                    <div><div className="dv-refcard"><span className="dv-eyebrow">WHY</span><h3>每次变更都记录原因</h3><p>只有出现需求变化、质量问题或新增研究证据，才形成 Change Record 与独立评测。</p></div>
                      <div className="dv-refcard"><span className="dv-eyebrow">EVIDENCE</span><h3>版本与证据的关系</h3><p>技术 Page → GitHub PR → 实际运行 → 指标 → 技术决策。没有明确关联的事件不自动推断因果。</p></div>
                      <div className="dv-callout"><strong>需要区分：</strong>已提交、审批通过、代码合并和部署生效是四种不同状态。</div>
                    </div>
                  </div>
                </>:<>
                  <div className="dv-filterbar"><label className="dv-search"><Search size={14}/><input value={changeSearch} onChange={e=>setChangeSearch(e.target.value)} placeholder="搜索变更原因、类型和模块"/></label><span className="dv-muted">点击记录查看前后 Diff 与审批状态</span></div>
                  <div className="dv-tablewrap"><table className="dv-table"><thead><tr><th>变更请求</th><th>对象 / 模块</th><th>风险</th><th>当前状态</th><th>提交者</th></tr></thead><tbody>{changeRows.map(x=><tr key={x.id} className="dv-clickrow" onClick={()=>openDetail("change",x.id)}><td><b>{x.title}</b><small>{x.id}</small></td><td>{x.kind} / {x.module_id}</td><td><Badge tone={x.risk==="high"?"red":x.risk==="medium"?"amber":"gray"}>{x.risk}</Badge></td><td><Badge tone={badgeTone(x.status)}>{toLabel(x.status)}</Badge></td><td>{x.created_by.slice(0,8)}</td></tr>)}</tbody></table></div>
                  {!changeRows.length&&<Empty>{changeTab==="approvals"?"暂无你有权限审批的申请。":"尚无匹配的变更申请。"}</Empty>}
                </>}
              </div>
            </>}
            {page==="workflows"&&<>
              <div className="dv-grid3">{workflows.map(x=><button key={x.id} type="button" className={"dv-panel dv-workflowcard"+(selectedWorkflow===x.id?" active":"")} onClick={()=>setSelectedWorkflow(x.id)}>
                <div className="dv-row"><span className="dv-eyebrow">{x.id}</span><Badge tone="gray">{x.status}</Badge></div><h3>{x.name}</h3><p>{x.scope}</p>
              </button>)}</div>
              {workflows.filter(x=>x.id===selectedWorkflow).map(w=><div className="dv-twocol" key={w.id}>
                <div className="dv-panel"><PanelHeader title={w.id+" · "+w.name+" 的工作流步骤"} sub={w.schedule}/><div className="dv-stepflow">{w.steps.map((step,i)=><span key={step} className="dv-step">{i+1}. {step}</span>)}</div>
                  <div className="dv-callout">这里展示的是设计工作流，而不是从生产环境读取的真实模型调用配置。发布流程仍需要版本快照和独立审核。</div></div>
                <div className="dv-panel"><PanelHeader title="运行配置快照" sub="只读 · 待连接实际配置"/><KV label="工作流版本" value="尚未核验"/><KV label="模型 Provider / ID" value="等待配置读取"/><KV label="Skill / Prompt" value="需要真实版本 SHA"/><KV label="关注来源版本" value="应关联已批准的 A/B/C 快照"/><KV label="调度周期" value={w.schedule}/><KV label="生产执行状态" value="未连接"/><KV label="API 密钥" value="仅能查看是否已配置，不显示密钥"/></div>
              </div>)}
              <SectionHeader title="设计中的受控发布链" sub="配置生效前必须经过工程与科研质量检查"/>
              <div className="dv-panel"><div className="dv-stepflow">{["配置草稿","前后差异","固定测试集","科研评审","独立审批","受控部署","回滚记录"].map(x=><span key={x} className="dv-step">{x}</span>)}</div></div>
            </>}
            {page==="settings"&&<>
              <div className="dv-twocol">
                <div className="dv-panel"><PanelHeader title="团队角色与管理范围" sub="现阶段角色映射"/>
                  <div className="dv-tablewrap"><table className="dv-table"><thead><tr><th>角色</th><th>查看</th><th>提交变更</th><th>审批</th></tr></thead><tbody>
                    {[["管理员 admin","是","是","只可审他人申请"],["研究成员 researcher","是","是","否"],["观察者 viewer","是","否","否"]].map(x=><tr key={x[0]}><td><b>{x[0]}</b></td><td>{x[1]}</td><td>{x[2]}</td><td>{x[3]}</td></tr>)}</tbody></table></div>
                  <div className="dv-callout">来源维护者、文档维护者、科研评审者等细分职责目前属于设计目标，尚未作为独立权限角色实现。</div>
                </div>
                <div className="dv-panel"><PanelHeader title="开发与部署事实"/><KV label="当前会话" value={session.member?.name+" · "+session.member?.role}/><KV label="UI 参考版本" value="已确认 HTML V0.2"/><KV label="前端工作分支" value={<External href="https://github.com/Hu-py/research-opportunity-workbench/pull/58">Draft PR #58</External>}/><KV label="学术采集器" value={<External href="https://github.com/Hu-py/research-opportunity-workbench/pull/57">Draft PR #57</External>}/><KV label="生产部署" value="未在管理台核验"/><KV label="GitHub 状态同步" value="尚未接入"/><KV label="后台数据" value="来自当前授权数据库"/></div>
              </div>
              <SectionHeader title="运维与开发交接" sub="维护手册、权限和历史决策应当可查询"/>
              <div className="dv-grid3">{[["运行 SOP","故障排查、重试、备份与权限说明。"],["受控发布与回退","保存审批人、版本标识、实际生效时间及回退步骤。"],["开发交接清单","维护责任人、当前 PR、待解决问题与技术规范。"]].map((x,i)=><div className="dv-panel" key={x[0]}><span className="dv-eyebrow">{["OPERATIONS","CHANGE CONTROL","HANDOVER"][i]}</span><h3>{x[0]}</h3><p className="dv-muted">{x[1]}</p></div>)}</div>
            </>}
          </>}
          <footer className="dv-footer"><span>Research Atlas · Development Studio · UI implementation based on approved V0.2</span><span>未连接的功能显式标注 · 所有变更需真实权限与审批</span></footer>
        </>}
      </div>
    </main>

    {detail&&<div className="dv-backdrop" onClick={closePopups}><aside className="dv-drawer" role="dialog" aria-modal="true" aria-label="研发对象详情" onClick={e=>e.stopPropagation()}>
      <div className="dv-drawerhead"><span className="dv-eyebrow">RESEARCH ATLAS · DETAIL</span><button type="button" aria-label="关闭详情" className="dv-xbtn" onClick={closePopups}><X size={20}/></button></div>
      {detail.kind==="source"&&(()=>{
        const item=designSources.find(x=>x.id===detail.id);
        if(!item)return <Empty>来源记录不存在。</Empty>;
        return <><h2>{item.name}</h2><p className="dv-muted">设计参考来源 · 不是已启用生产配置</p>
          <div className="dv-tabs">{["基本资料","采集表现","变更历史","关联研究"].map(x=><button key={x} type="button" className={"dv-tab"+(detailTab===x?" active":"")} onClick={()=>setDetailTab(x)}>{x}</button>)}</div>
          {detailTab==="基本资料"&&<><KV label="来源类型" value={item.kind}/><KV label="类别" value={groupTitles[item.group]}/><KV label="科研关注理由" value={item.reason}/><KV label="推荐发现渠道" value={item.channel}/><KV label="官网" value={<External href={item.url}>打开官方网站</External>}/></>}
          {detailTab==="采集表现"&&<><KV label="来源身份" value="待正式目录核验"/><KV label="当前参考标签" value={item.status}/><div className="dv-callout">只有 SCS、EPB 和 JMLR 的特定哨兵样本在 2026-11-14 做过真实 API 对照，不能推断其他期刊的总量覆盖。</div></>}
          {detailTab==="变更历史"&&<div className="dv-callout">当前只是设计建议清单，审批后正式配置的版本发布还未实现。每次修改必须关联 Change Record。</div>}
          {detailTab==="关联研究"&&<External href="https://github.com/Hu-py/research-opportunity-workbench/blob/feature/atlas-three-source-ai-workflow-v01/experiments/atlas_pilot_2026_11_14/REPORT.md">查看已知来源采集实验</External>}
          {canWrite&&<div className="dv-draweractions"><button type="button" className="dv-btn dv-primary" onClick={()=>openModal("source",undefined,undefined,undefined,{name:item.name,group:groupKey[item.group],url:item.url,reason:"建议纳入 "+groupTitles[item.group]+"；需确认官方身份和采集覆盖。",operation:"add"})}>基于此来源提出申请</button></div>}
        </>;
      })()}
      {detail.kind==="document"&&(()=>{
        const doc=documents.find(x=>x.id===detail.id);
        if(!doc)return <Empty>文档不存在。</Empty>;
        return <><h2>{doc.title}</h2><p className="dv-muted">{doc.module_id} · 已登记文档</p>
          <div className="dv-tabs">{["基本信息","版本与审阅","关联模块"].map(x=><button type="button" key={x} className={"dv-tab"+(detailTab===x?" active":"")} onClick={()=>setDetailTab(x)}>{x}</button>)}</div>
          {detailTab==="基本信息"&&<><KV label="文档类型" value={categoryTitles[doc.category]||doc.category}/><KV label="状态" value={toLabel(doc.status)}/><KV label="维护者 ID" value={doc.owner_id}/><KV label="权威原件" value={<External href={doc.authoritative_url}>打开 Page / GitHub</External>}/></>}
          {detailTab==="版本与审阅"&&<><KV label="登记修订" value={doc.revision_ref||"未记录"}/><KV label="登记日期" value={dateLabel(doc.created_at)}/><div className="dv-callout">只登记文档索引，不自动同步原文。正式文档版本需审核与权威来源核对。</div></>}
          {detailTab==="关联模块"&&<KV label="能力模块" value={moduleLabels[doc.module_id]||doc.module_id}/>}
          {canWrite&&<div className="dv-draweractions"><button type="button" className="dv-btn dv-primary" onClick={()=>openModal("docRevision",doc.id)}>提出文档修订</button></div>}
        </>;
      })()}
      {detail.kind==="change"&&(()=>{
        const change=changes.find(x=>x.id===detail.id);
        if(!change)return <Empty>变更不存在。</Empty>;
        return <><h2>{change.title}</h2><p className="dv-muted">{change.id} · {moduleLabels[change.module_id]||change.module_id}</p>
          <div className="dv-tabs">{["为什么修改","前后 Diff","影响与证据","审批与生效"].map(x=><button type="button" key={x} className={"dv-tab"+(detailTab===x?" active":"")} onClick={()=>setDetailTab(x)}>{x}</button>)}</div>
          {detailTab==="为什么修改"&&<><KV label="类型 / 风险" value={change.kind+" / "+change.risk}/><p>{change.reason}</p><KV label="提交者" value={change.created_by}/><KV label="提交时间" value={dateLabel(change.created_at)}/></>}
          {detailTab==="前后 Diff"&&<><h3>变更提案</h3><pre className="dv-pre">{JSON.stringify(change.proposed,null,2)}</pre><div className="dv-callout">当前保存的是提案内容；实际 GitHub 文件 Diff 需链接 PR/Commit，不能从提案文本推定代码已改变。</div></>}
          {detailTab==="影响与证据"&&<><KV label="关联问题" value={change.issue_id||"未关联"}/><KV label="模块" value={change.module_id}/><div className="dv-callout">正式科研影响评估需关联固定实验输入、运行证据和审查意见。</div></>}
          {detailTab==="审批与生效"&&<><KV label="审批状态" value={<Badge tone={badgeTone(change.status)}>{toLabel(change.status)}</Badge>}/><div className="dv-callout">管理员批准只产生待发布状态。代码合并、部署及配置生效仍属于独立事件。</div>
            {canApprove&&change.status==="submitted"&&change.created_by!==actorId&&<div className="dv-draweractions">{[
              ["批准","approve"],["退回","request_changes"],["拒绝","reject"]
            ].map(([text,action])=><button className="dv-btn" key={action} onClick={()=>openModal("approval",change.id,undefined,action as Modal["action"])}>{text}</button>)}</div>}
            {canApprove&&change.created_by===actorId&&<p className="dv-muted">申请人不能审核自己的变更。请交由另一位管理员。</p>}
          </>}
        </>;
      })()}
      {detail.kind==="module"&&<><h2>{moduleLabels[detail.id]||detail.id}</h2><p className="dv-muted">{detail.id} · {moduleScopes[detail.id]}</p>
        <div className="dv-tabs">{["概览","问题与实验","版本与文档"].map(x=><button key={x} type="button" className={"dv-tab"+(detailTab===x?" active":"")} onClick={()=>setDetailTab(x)}>{x}</button>)}</div>
        {detailTab==="概览"&&<><KV label="已登记问题" value={issues.filter(x=>x.module_id===detail.id).length}/><KV label="变更记录" value={changes.filter(x=>x.module_id===detail.id).length}/><KV label="实验记录" value={experiments.filter(x=>x.module_id===detail.id).length}/><KV label="当前正式版本" value="尚未在 Development Studio 核验"/></>}
        {detailTab==="问题与实验"&&<><SectionHeader title="已登记问题"/>{issues.filter(x=>x.module_id===detail.id).map(x=><p key={x.id}>{x.title} · {toLabel(x.status)}</p>)}<SectionHeader title="已登记实验"/>{experiments.filter(x=>x.module_id===detail.id).map(x=><p key={x.id}>{x.title}</p>)}</>}
        {detailTab==="版本与文档"&&<><External href={"/devstudio/changes?module="+encodeURIComponent(detail.id)}>查看关联版本链</External><div className="dv-callout">模块版本必须区别实验分支、已合并代码与实际部署状态。</div></>}
        <div className="dv-draweractions"><Link className="dv-btn dv-primary" href={"/devstudio/changes?module="+encodeURIComponent(detail.id)}>查看模块演化链</Link></div>
      </>}
    </aside></div>}
    {modal&&<div className="dv-backdrop" onClick={closePopups}><div className="dv-dialog" role="dialog" aria-modal="true" aria-label="研发管理操作" onClick={e=>e.stopPropagation()}>
      <div className="dv-dialoghead"><div><span className="dv-eyebrow">DEVELOPMENT STUDIO · ACTION</span><h2>{{
        search:"跨模块搜索",source:"提出学术来源变更",document:"登记权威文档",docRevision:"提出文档修订",
        experiment:"创建科研实验",run:"关联实际运行",evaluation:"追加人工评审",
        change:"提交技术变更",approval:"独立审核变更",issue:"登记研发问题",info:"设计和权限说明"
      }[modal.type]}</h2></div><button type="button" className="dv-xbtn" onClick={closePopups}><X size={20}/></button></div>
      {modal.type==="search"?<div className="dv-command">
        <label className="dv-search"><Search size={16}/><input autoFocus value={commandQuery} onChange={e=>setCommandQuery(e.target.value)}
          placeholder="搜索能力模块、期刊、实验、文档或变更编号"/></label>
        <div className="dv-commanditems">{searchItems.map(x=><button type="button" key={x.kind+"-"+x.id}
          onClick={()=>openSearchResult(x.kind,x.id)}><span><strong>{x.title}</strong><small>{x.sub} · {x.id}</small></span><ArrowRight size={15}/></button>)}
          {!searchItems.length&&<Empty>没有匹配记录。</Empty>}
        </div>
        <p className="dv-muted">搜索范围包括已登记的研发数据与明确标注的来源设计参考。</p>
      </div>:modal.type==="info"?<p>{modal.message}</p>:<div className="dv-formgrid">
        {modal.type==="source"&&<>
          <label>变更方式<select value={form.operation||"add"} onChange={e=>setValue("operation",e.target.value)}><option value="add">新增关注来源</option><option value="pause">暂停</option><option value="reclassify">重分类</option><option value="update">更新信息</option></select></label>
          <label>关注类别<select value={form.group||"urban_science"} onChange={e=>setValue("group",e.target.value)}><option value="planning_application">A · 规划应用</option><option value="urban_science">B · 城市科学</option><option value="computational_methods">C · 计算方法</option></select></label>
          <label className="dv-full">期刊、会议或作者名称<input value={form.name||""} onChange={e=>setValue("name",e.target.value)}/></label>
          <label className="dv-full">官网（可选）<input value={form.url||""} onChange={e=>setValue("url",e.target.value)} placeholder="https://..."/></label>
          <label className="dv-full">科学关注理由<textarea rows={4} value={form.reason||""} onChange={e=>setValue("reason",e.target.value)} placeholder="请说明为什么值得增加，以及对现有采集范围的影响。"/></label>
        </>}
        {modal.type==="document"&&<>
          <label className="dv-full">文档标题<input value={form.title||""} onChange={e=>setValue("title",e.target.value)}/></label>
          <label>文档类别<select value={form.category||"architecture"} onChange={e=>setValue("category",e.target.value)}>{Object.entries(categoryTitles).map(([k,v])=><option value={k} key={k}>{v}</option>)}</select></label>
          <label>对应模块<select value={form.module||"PLATFORM"} onChange={e=>setValue("module",e.target.value)}>{Object.entries(moduleLabels).map(([k,v])=><option value={k} key={k}>{v}</option>)}</select></label>
          <label className="dv-full">权威 Page / GitHub 地址<input value={form.url||""} onChange={e=>setValue("url",e.target.value)} placeholder="https://chatgpt.com/space/page_..."/></label>
          <label>修订版本<input value={form.revision||""} onChange={e=>setValue("revision",e.target.value)}/></label>
        </>}
        {modal.type==="docRevision"&&<label className="dv-full">修改原因和希望调整的内容<textarea rows={5} value={form.reason||""} onChange={e=>setValue("reason",e.target.value)}/></label>}
        {modal.type==="experiment"&&<>
          <label>所属模块<select value={form.module||"DISCOVERY"} onChange={e=>setValue("module",e.target.value)}>{Object.entries(moduleLabels).map(([k,v])=><option value={k} key={k}>{v}</option>)}</select></label>
          <label className="dv-full">实验标题<input value={form.title||""} onChange={e=>setValue("title",e.target.value)}/></label>
          <label className="dv-full">假设和预期验证结果<textarea rows={4} value={form.hypothesis||""} onChange={e=>setValue("hypothesis",e.target.value)}/></label>
          <label>对照基线<input value={form.baseline||""} onChange={e=>setValue("baseline",e.target.value)}/></label>
          <label>固定输入快照引用<input value={form.snapshot||""} onChange={e=>setValue("snapshot",e.target.value)}/></label>
          <label className="dv-full">关联变更（可选）<select value={form.change||""} onChange={e=>setValue("change",e.target.value)}><option value="">不关联</option>{changes.map(x=><option key={x.id} value={x.id}>{x.title}</option>)}</select></label>
        </>}
        {modal.type==="run"&&<>
          <label className="dv-full">本仓库 GitHub Actions Run 链接<input value={form.url||""} onChange={e=>setValue("url",e.target.value)} placeholder="https://github.com/Hu-py/research-opportunity-workbench/actions/runs/…"/></label>
          <label>代码 Commit SHA（可选）<input value={form.sha||""} onChange={e=>setValue("sha",e.target.value)}/></label>
          <label className="dv-full">运行说明<textarea rows={2} value={form.note||""} onChange={e=>setValue("note",e.target.value)}/></label>
        </>}
        {modal.type==="evaluation"&&<>
          <label>人工科研质量评分（0–5）<select value={form.score||"3"} onChange={e=>setValue("score",e.target.value)}>{[0,1,2,3,4,5].map(x=><option value={x} key={x}>{x}</option>)}</select></label>
          <label className="dv-full">证据与结论限制<textarea rows={4} value={form.reason||""} onChange={e=>setValue("reason",e.target.value)} placeholder="说明评分依据、研究局限，不能只给分数。"/></label>
        </>}
        {modal.type==="change"&&<>
          <label>变更类型<select value={form.kind||"code"} onChange={e=>setValue("kind",e.target.value)}><option value="code">代码</option><option value="workflow">AI 工作流</option><option value="document">文档</option><option value="other">其他</option></select></label>
          <label>所属模块<select value={form.module||"DISCOVERY"} onChange={e=>setValue("module",e.target.value)}>{Object.entries(moduleLabels).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
          <label className="dv-full">变更标题<input value={form.title||""} onChange={e=>setValue("title",e.target.value)}/></label>
          <label className="dv-full">为什么需要修改<textarea rows={4} value={form.reason||""} onChange={e=>setValue("reason",e.target.value)} placeholder="说明具体问题、真实证据和预期效果。"/></label>
          <label className="dv-full">修改方案与影响<textarea rows={2} value={form.proposal||""} onChange={e=>setValue("proposal",e.target.value)}/></label>
        </>}
        {modal.type==="issue"&&<>
          <label>所属模块<select value={form.module||"DISCOVERY"} onChange={e=>setValue("module",e.target.value)}>{Object.entries(moduleLabels).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
          <label>严重程度<select value={form.severity||"medium"} onChange={e=>setValue("severity",e.target.value)}><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select></label>
          <label className="dv-full">问题标题<input value={form.title||""} onChange={e=>setValue("title",e.target.value)}/></label>
          <label className="dv-full">问题和现有证据<textarea rows={4} value={form.reason||""} onChange={e=>setValue("reason",e.target.value)}/></label>
        </>}
        {modal.type==="approval"&&<>
          <p className="dv-full dv-muted">你正在对他人的变更记录做独立审查。审核结论会永久留痕，但不会自动发布到生产。</p>
          <label className="dv-full">审核依据与理由<textarea rows={5} value={form.reason||""} onChange={e=>setValue("reason",e.target.value)}/></label>
        </>}
      </div>}
      <div className="dv-dialogactions"><button type="button" className="dv-btn" onClick={closePopups}>关闭</button>{modal.type!=="info"&&modal.type!=="search"&&<button type="button" disabled={busy||!canWrite} className="dv-btn dv-primary" onClick={()=>void submitModal()}>{busy?"提交中…":"确认提交"}</button>}</div>
      <p className="dv-muted dv-dialognote">所有变更以真实后端成功响应为准；审批不会自动发布。</p>
    </div></div>}
    {reviewOpen&&<div className="dv-backdrop" onClick={()=>setReviewOpen(false)}><aside className="dv-drawer" role="dialog" aria-modal="true" aria-label="界面逐页评审" onClick={e=>e.stopPropagation()}>
      <div className="dv-drawerhead"><span className="dv-eyebrow">UI DESIGN REVIEW</span><button className="dv-xbtn" aria-label="关闭" onClick={()=>setReviewOpen(false)}><X size={20}/></button></div>
      <h2>逐页反馈</h2><p className="dv-muted">当前页面：{titles.title}。这里的反馈只在浏览器会话内保留，不写入正式研发数据库。</p>
      <div className="dv-tabs">{(["认可","需修改","待讨论"] as Feedback[]).map(s=><button key={s} className={"dv-tab"+(feedbackStatus===s?" active":"")} onClick={()=>setFeedbackStatus(s)}>{s}</button>)}</div>
      <label className="dv-formlabel">修改意见<textarea rows={6} value={feedbackNote} onChange={e=>setFeedbackNote(e.target.value)} placeholder="例如：统计卡片需要直接筛选下方列表。"/></label>
      <div className="dv-draweractions"><button className="dv-btn dv-primary" onClick={feedbackSave}>保存本次反馈</button><button className="dv-btn" onClick={feedbackExport}>导出 Markdown</button></div>
      <SectionHeader title="页面评审进度"/>{navItems.map(x=><p key={x.id} className="dv-reviewline"><span>{x.label}</span><Badge tone={pageFeedback[x.id]?.status==="认可"?"green":"gray"}>{pageFeedback[x.id]?.status||"待讨论"}</Badge></p>)}
    </aside></div>}
  </div>;
}
