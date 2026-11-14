"use client";

import Link from "next/link";
import {useCallback, useEffect, useMemo, useState} from "react";
import {usePathname} from "next/navigation";
import {
  Activity, ArrowLeft, ArrowRight, BookOpen, Check, ChevronRight, ClipboardCheck,
  Clock3, Database, ExternalLink, FileText, FlaskConical, GitBranch, LayoutDashboard,
  LockKeyhole, Plus, RefreshCw, Search, ShieldCheck, Workflow, X,
} from "lucide-react";
import {api} from "@/lib/api";
import "./devstudio.css";

type Member = {id:string;name:string;role:"admin"|"researcher"|"viewer"};
type Session = {authenticated:boolean;team:boolean;member:Member|null};
type Module = {id:string;name:string;scope:string};
type Overview = {modules:Module[];counts:{open_issues:number;pending_changes:number;experiments:number;indexed_documents:number};deployment_status:string;note:string};
type Row = {id:string;module_id:string;created_at:string};
type Change = Row & {kind:string;title:string;reason:string;status:string;risk:string;created_by:string;issue_id:string;proposed:Record<string,unknown>};
type Source = {id:string;name:string;abbreviation:string;kind:string;domain:string;enabled:boolean;openalex_source_id:string;resolution_status:string;source_url:string;atlas_source_groups:string[];atlas_classification_status:string};
type SourceResponse = {legacy_registry:Source[];source_proposals:Change[];warning:string};
type Document = Row & {title:string;category:string;authoritative_url:string;revision_ref:string;status:string;owner_id:string};
type Experiment = Row & {title:string;hypothesis:string;baseline:string;status:string;input_snapshot_ref:string;change_id:string;metrics:string[]};
type RunRef = {id:string;experiment_id:string;kind:string;external_url:string;status:string;note:string;code_sha:string;created_at:string};
type Issue = Row & {title:string;description:string;severity:string;status:string};
type Decision = {id:string;change_id:string;decision:string;reason:string;reviewer_id:string;created_at:string};
type Lineage = {issues:Issue[];changes:Change[];experiments:Experiment[];runs:RunRef[];decisions:Decision[]};
type Section = "overview"|"sources"|"documents"|"experiments"|"changes";

const moduleNames:Record<string,string> = {
  DISCOVERY:"文献发现与来源核验", PAPER_KNOWLEDGE:"论文知识抽取",
  SIGNAL_L1:"跨论文科研信号", DEEP_READ_L2:"代表论文深读",
  IDEA_L3:"方法迁移与研究机会", TEAM_FIT:"团队科研能力匹配",
  DELIVERY:"交付、审核与反馈", PLATFORM:"平台与基础设施",
};
const groupNames:Record<string,string> = {
  planning_application:"A · 规划应用",
  urban_science:"B · 城市科学",
  computational_methods:"C · 计算方法",
};
const navItems:{id:Section;name:string;sub:string;icon:typeof LayoutDashboard}[] = [
  {id:"overview",name:"研发总览",sub:"模块与待办",icon:LayoutDashboard},
  {id:"sources",name:"学术来源与配置",sub:"期刊 · 会议 · 作者",icon:BookOpen},
  {id:"documents",name:"文档中心",sub:"规范与版本",icon:FileText},
  {id:"experiments",name:"实验与评测",sub:"设计 · 运行 · 证据",icon:FlaskConical},
  {id:"changes",name:"版本与审批",sub:"问题 · 变更 · 决策",icon:GitBranch},
];
const statusNames:Record<string,string> = {
  submitted:"待审批", approved_pending_release:"已批准·待发布",
  rejected:"已拒绝", needs_revision:"需修改", open:"待处理",
  planned:"已登记·待执行", unverified:"已关联·未核验",
  indexed_draft:"已索引·待审核",
};
function label(status:string){return statusNames[status] || status.replaceAll("_"," ");}
function day(value?:string){return value?value.slice(0,10):"—";}
function humanError(e:unknown){return e instanceof Error?e.message:"操作未完成";}
function LinkExternal({href,children}:{href:string;children:React.ReactNode}){
  return <a className="ds-link" href={href} target="_blank" rel="noopener noreferrer">{children}<ExternalLink size={13}/></a>;
}

export default function DevelopmentStudio(){
  const pathname=usePathname();
  const segment=pathname.split("/")[2] as Section|undefined;
  const section:Section=navItems.some(x=>x.id===segment)?segment!:"overview";
  const [session,setSession]=useState<Session|null>(null);
  const [overview,setOverview]=useState<Overview|null>(null);
  const [sources,setSources]=useState<SourceResponse|null>(null);
  const [documents,setDocuments]=useState<Document[]>([]);
  const [experiments,setExperiments]=useState<Experiment[]>([]);
  const [changes,setChanges]=useState<Change[]>([]);
  const [issues,setIssues]=useState<Issue[]>([]);
  const [busy,setBusy]=useState(false);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [showForm,setShowForm]=useState(false);
  const [search,setSearch]=useState("");
  const [group,setGroup]=useState("all");
  const [moduleId,setModuleId]=useState("DISCOVERY");
  const [lineage,setLineage]=useState<Lineage|null>(null);
  const [selectedExperiment,setSelectedExperiment]=useState<Experiment|null>(null);
  const [runs,setRuns]=useState<RunRef[]>([]);
  const [sourceName,setSourceName]=useState("");
  const [sourceGroup,setSourceGroup]=useState("urban_science");
  const [sourceReason,setSourceReason]=useState("");
  const [sourceOperation,setSourceOperation]=useState("add");
  const [documentTitle,setDocumentTitle]=useState("");
  const [documentUrl,setDocumentUrl]=useState("");
  const [documentCategory,setDocumentCategory]=useState("architecture");
  const [experimentTitle,setExperimentTitle]=useState("");
  const [experimentHypothesis,setExperimentHypothesis]=useState("");
  const [experimentBaseline,setExperimentBaseline]=useState("");
  const [experimentInput,setExperimentInput]=useState("");
  const [runUrl,setRunUrl]=useState("");
  const [changeTitle,setChangeTitle]=useState("");
  const [changeReason,setChangeReason]=useState("");
  const [issueTitle,setIssueTitle]=useState("");
  const [issueDescription,setIssueDescription]=useState("");
  const canEdit=!!session?.member && ["admin","researcher"].includes(session.member.role);
  const canApprove=session?.member?.role==="admin";

  const load=useCallback(async (target:Section)=>{
    setLoading(true);setError("");
    try{
      if(target==="overview")setOverview(await api<Overview>("devstudio/overview"));
      if(target==="sources")setSources(await api<SourceResponse>("devstudio/sources"));
      if(target==="documents")setDocuments((await api<{items:Document[]}>("devstudio/documents")).items);
      if(target==="experiments")setExperiments((await api<{items:Experiment[]}>("devstudio/experiments")).items);
      if(target==="changes"){
        const [c,i]=await Promise.all([
          api<{items:Change[]}>("devstudio/changes"),
          api<{items:Issue[]}>("devstudio/issues"),
        ]);
        setChanges(c.items);setIssues(i.items);
      }
    }catch(e){setError(humanError(e));}finally{setLoading(false);}
  },[]);

  useEffect(()=>{
    fetch("/api/session",{cache:"no-store"}).then(r=>r.json())
      .then((s:Session)=>setSession(s)).catch(()=>setSession({authenticated:false,team:false,member:null}));
  },[]);
  useEffect(()=>{
    if(!session?.authenticated||!session.team){setLoading(false);return;}
    void load(section);
    setSearch("");setShowForm(false);setNotice("");setError("");
  },[section,session?.authenticated,session?.team,load]);
  const selectedName=navItems.find(x=>x.id===section)?.name || "研发总览";

  async function submit(work:()=>Promise<unknown>,success:string){
    setBusy(true);setError("");setNotice("");
    try{await work();setShowForm(false);setNotice(success);await load(section);}
    catch(e){setError(humanError(e));}
    finally{setBusy(false);}
  }
  async function openExperiment(x:Experiment){
    setSelectedExperiment(x);setRuns([]);setError("");
    try{setRuns((await api<{items:RunRef[]}>("devstudio/experiments/"+x.id+"/runs")).items);}
    catch(e){setError(humanError(e));}
  }
  async function loadLineage(id:string){
    setModuleId(id);
    try{setLineage(await api<Lineage>("devstudio/lineage/"+id));}
    catch(e){setError(humanError(e));}
  }
  async function decide(x:Change,decision:"approve"|"reject"|"request_changes"){
    const reason=window.prompt(
      decision==="approve"?"请填写批准依据。批准不会直接修改生产配置：":"请填写审核理由：",
      ""
    );
    if(!reason || reason.trim().length<8)return;
    if(x.created_by===session?.member?.id){
      setError("申请人不能审核自己的变更。请让另一位管理员审阅。");return;
    }
    if(!window.confirm("确认记录该审核决定？历史记录将保留，并且不会自动发布到生产环境。"))return;
    await submit(()=>api("devstudio/changes/"+x.id+"/decisions",{
      method:"POST",body:JSON.stringify({decision,reason})
    }),"已记录审批意见；正式生效需要受控发布流程。");
  }

  const visibleSources=useMemo(()=>sources?.legacy_registry.filter(x=>
    (x.name+" "+x.abbreviation+" "+x.domain).toLowerCase().includes(search.toLowerCase())
  )||[],[sources,search]);
  const visibleProposals=useMemo(()=>sources?.source_proposals.filter(x=>
    (group==="all"||(Array.isArray(x.proposed.source_groups)&&x.proposed.source_groups.includes(group)))&&
    (x.title+" "+x.reason).toLowerCase().includes(search.toLowerCase())
  )||[],[sources,search,group]);
  const visibleDocuments=useMemo(()=>documents.filter(x=>
    (x.title+" "+x.category+" "+x.module_id).toLowerCase().includes(search.toLowerCase())
  ),[documents,search]);
  const visibleExperiments=useMemo(()=>experiments.filter(x=>
    (x.title+" "+x.hypothesis+" "+x.module_id).toLowerCase().includes(search.toLowerCase())
  ),[experiments,search]);
  const visibleChanges=useMemo(()=>changes.filter(x=>
    (x.title+" "+x.kind+" "+x.reason).toLowerCase().includes(search.toLowerCase())
  ),[changes,search]);

  return <div className="ds-shell">
    <aside className="ds-sidebar">
      <Link href="/" className="ds-brand">
        <div className="ds-brandmark"><Workflow size={22}/></div>
        <div><strong>Research Atlas</strong><small>DEVELOPMENT STUDIO</small></div>
      </Link>
      <div className="ds-side-label">研发管理</div>
      <nav aria-label="研发管理导航" className="ds-nav">
        {navItems.map(item=><Link href={item.id==="overview"?"/devstudio":"/devstudio/"+item.id}
          key={item.id} aria-current={section===item.id?"page":undefined}
          className={"ds-navitem "+(section===item.id?"ds-navactive":"")}>
          <item.icon size={18}/>
          <span><strong>{item.name}</strong><small>{item.sub}</small></span>
        </Link>)}
      </nav>
      <div className="ds-navbottom">
        <Link href="/" className="ds-back"><ArrowLeft size={16}/> 返回科研工作台</Link>
        <div className="ds-person"><ShieldCheck size={16}/>
          <span>{session?.member?.name||"未登录"}<small>{session?.member?.role||"需要团队身份"}</small></span>
        </div>
      </div>
    </aside>

    <main className="ds-main">
      <div className="ds-topbar">
        <div><span className="ds-crumb">Research Atlas</span><ChevronRight size={14}/><strong>{selectedName}</strong></div>
        <div className="ds-top-actions"><span className="ds-readonly">P0 · 研发治理</span>
          <button type="button" className="ds-iconbtn" title="刷新当前数据" onClick={()=>void load(section)}><RefreshCw size={17}/></button>
        </div>
      </div>
      <div className="ds-content">
        {!session && <div className="ds-card">正在检查团队登录状态…</div>}
        {session && (!session.authenticated||!session.team) && <div className="ds-card ds-locked">
          <LockKeyhole size={31}/>
          <h2>需要团队登录</h2>
          <p>Development Studio 含变更审批和研发数据。请返回工作台使用团队账号登录，并确保后端启用了 TEAM_AUTH_ENABLED。</p>
          <Link href="/" className="ds-btn ds-primary">返回工作台 <ArrowRight size={15}/></Link>
        </div>}
        {session?.authenticated && session.team && <>
          <header className="ds-heading">
            <div><span className="ds-eyebrow">DEVELOPMENT GOVERNANCE</span><h1>{selectedName}</h1>
              <p>{section==="overview"?"研发进度、实验问题和待处理变更的统一入口。":
                section==="sources"?"维护来源提案，不直接改变生产扫描；旧 Radar 来源与新 A/B/C 分类分开。":
                section==="documents"?"索引 Page 和 GitHub 中的权威文档，留下修订责任与版本。":
                section==="experiments"?"建立可复现实验，将实际运行、输入快照和评测依据关联。":
                "记录为何修改、如何验证、谁审批以及哪些变更尚未生效。"}</p></div>
            <div className="ds-headeractions">
              {canEdit && section!=="overview" && <button type="button" className="ds-btn ds-primary"
                onClick={()=>{setShowForm(x=>!x);setError("");}}><Plus size={16}/>{section==="sources"?"提出来源变更":section==="documents"?"登记文档":section==="experiments"?"登记实验":"提交变更"}</button>}
            </div>
          </header>
          {error&&<div role="alert" className="ds-message ds-error"><X size={16}/>{error}<button onClick={()=>setError("")} aria-label="关闭错误">×</button></div>}
          {notice&&<div role="status" className="ds-message ds-success"><Check size={16}/>{notice}</div>}
          {loading && <div className="ds-card">读取真实研发记录中…</div>}

          {!loading && section==="overview" && overview && <>
            <div className="ds-stats">
              {[
                ["研发模块",overview.modules.length,"结构清单"],
                ["待处理问题",overview.counts.open_issues,"已登记"],
                ["待审批变更",overview.counts.pending_changes,"未生效"],
                ["实验记录",overview.counts.experiments,"已登记"],
              ].map(([name,n,desc])=><div className="ds-stat" key={String(name)}>
                <span>{name}</span><strong>{n}</strong><small>{desc}</small>
              </div>)}
            </div>
            <div className="ds-sectionhead"><h2>能力模块</h2><span>模块状态只反映已登记证据，不表示 CI 或科研验收通过</span></div>
            <div className="ds-modulegrid">{overview.modules.map(m=><button key={m.id} type="button" className="ds-module"
                onClick={()=>{void loadLineage(m.id);window.location.href="/devstudio/changes";}}>
              <span className="ds-modulecode">{m.id}</span><h3>{m.name}</h3>
              <p>{m.scope}</p><span className="ds-subtle">当前正式版本：尚未登记 <ArrowRight size={14}/></span>
            </button>)}</div>
            <div className="ds-card"><strong>数据状态说明</strong><p>本页仅统计 Development Studio 的真实记录。现有 GitHub PR、旧实验和已部署状态不会被自动当作“完成”，需要明确关联并核验。</p></div>
          </>}

          {!loading && section==="sources" && sources && <>
            <div className="ds-tabs">
              {["all",...Object.keys(groupNames)].map(g=><button type="button" key={g}
                className={group===g?"ds-tab active":"ds-tab"} onClick={()=>setGroup(g)}>{g==="all"?"全部提案":groupNames[g]}</button>)}
            </div>
            {showForm&&<div className="ds-card ds-form">
              <h2>提出来源配置变更</h2>
              <p>提交后进入审批；不会自动写入旧 Radar 来源表或 A/B/C 正式采集配置。</p>
              <div className="ds-formgrid">
                <label>来源名称<input value={sourceName} onChange={e=>setSourceName(e.target.value)} placeholder="例如：Cities"/></label>
                <label>变更类型<select value={sourceOperation} onChange={e=>setSourceOperation(e.target.value)}>
                  <option value="add">新增</option><option value="pause">暂停</option>
                  <option value="reclassify">调整分类</option><option value="update">更新元信息</option>
                </select></label>
                <label>来源分类<select value={sourceGroup} onChange={e=>setSourceGroup(e.target.value)}>
                  {Object.entries(groupNames).map(([k,v])=><option value={k} key={k}>{v}</option>)}
                </select></label>
                <label className="full">修改原因<textarea rows={3} value={sourceReason} onChange={e=>setSourceReason(e.target.value)} placeholder="说明为何要新增或修改，对现有检索有哪些影响。"/></label>
              </div>
              <div className="ds-formactions"><button type="button" className="ds-btn" onClick={()=>setShowForm(false)}>取消</button>
                <button disabled={busy} className="ds-btn ds-primary" onClick={()=>void submit(()=>
                  api("devstudio/changes",{method:"POST",body:JSON.stringify({
                    module_id:"DISCOVERY",kind:"source",title:sourceOperation+" · "+sourceName,
                    reason:sourceReason,proposed:{operation:sourceOperation,name:sourceName,source_groups:[sourceGroup]}
                  })}),"来源变更申请已保存，等待独立审核。")}>提交申请</button></div>
            </div>}
            <div className="ds-sectionhead"><h2>新三来源维护申请</h2><span>{visibleProposals.length} 项 · 申请不等于正式生效</span></div>
            <div className="ds-card ds-list">
              {visibleProposals.length?visibleProposals.map(x=><div className="ds-listrow" key={x.id}>
                <div><strong>{x.title}</strong><small>{Array.isArray(x.proposed.source_groups)?
                  x.proposed.source_groups.map(g=>groupNames[String(g)]||String(g)).join(" / "):"未分类"} · {day(x.created_at)}</small>
                  <p>{x.reason}</p></div><span className="ds-pill">{label(x.status)}</span></div>):
                <div className="ds-empty">当前分类尚无维护申请。可以提交一条新来源候选。</div>}
            </div>
            <div className="ds-sectionhead"><h2>现有期刊与会议注册表</h2><span>旧版资料 · 尚未迁移为新 A/B/C 来源配置</span></div>
            <div className="ds-search"><Search size={16}/><input aria-label="搜索旧来源" placeholder="按期刊、会议或学科搜索" value={search} onChange={e=>setSearch(e.target.value)}/></div>
            <div className="ds-card ds-tablewrap"><table className="ds-table"><thead><tr>
              <th>名称</th><th>类型</th><th>学科</th><th>OpenAlex</th><th>状态</th>
              </tr></thead><tbody>{visibleSources.slice(0,100).map(x=><tr key={x.id}>
                <td><strong>{x.name}</strong><small>{x.abbreviation}</small></td>
                <td>{x.kind}</td><td>{x.domain}</td>
                <td>{x.resolution_status==="resolved"?"已解析":"未核实"}</td>
                <td><span className="ds-pill">新三源未分类</span></td>
              </tr>)}</tbody></table>
              {!visibleSources.length&&<div className="ds-empty">没有匹配的来源</div>}
              {visibleSources.length>100&&<div className="ds-tablefoot">先显示前 100 项，请进一步搜索以缩小范围。</div>}
            </div>
          </>}

          {!loading && section==="documents" && <>
            {showForm&&<div className="ds-card ds-form">
              <h2>登记权威文档索引</h2><p>仅保存 Page / GitHub 链接，不复制私有 Page 正文。</p>
              <div className="ds-formgrid">
                <label>文档标题<input value={documentTitle} onChange={e=>setDocumentTitle(e.target.value)} placeholder="AI 工作流架构 V0.3"/></label>
                <label>分类<select value={documentCategory} onChange={e=>setDocumentCategory(e.target.value)}>
                  {Object.entries({product:"产品需求",architecture:"技术架构",data:"数据与 API",evaluation:"评测与实验",decision:"ADR 技术决策",operations:"运行与交接"}).map(([k,v])=><option key={k} value={k}>{v}</option>)}
                </select></label>
                <label>关联模块<select value={moduleId} onChange={e=>setModuleId(e.target.value)}>{Object.entries(moduleNames).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
                <label className="full">权威 Page 或 GitHub URL<input value={documentUrl} onChange={e=>setDocumentUrl(e.target.value)} placeholder="https://chatgpt.com/space/page_..."/></label>
              </div><div className="ds-formactions"><button className="ds-btn" onClick={()=>setShowForm(false)}>取消</button>
                <button disabled={busy} className="ds-btn ds-primary" onClick={()=>void submit(()=>api("devstudio/documents",{method:"POST",
                  body:JSON.stringify({module_id:moduleId,title:documentTitle,category:documentCategory,authoritative_url:documentUrl})}),
                  "已登记文档索引，原文仍由 Page/GitHub 管理。")}>登记索引</button></div>
            </div>}
            <div className="ds-search"><Search size={16}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="搜索文档名称、分类或模块"/></div>
            <div className="ds-card ds-list">
              {visibleDocuments.length?visibleDocuments.map(d=><div className="ds-listrow" key={d.id}>
                <div><span className="ds-modulecode">{d.category} / {d.module_id}</span>
                  <strong>{d.title}</strong><small>{day(d.created_at)} · 负责人：{d.owner_id.slice(0,8)}</small>
                  <LinkExternal href={d.authoritative_url}>打开权威文档</LinkExternal></div>
                <span className="ds-pill">{label(d.status)}</span>
              </div>):<div className="ds-empty">尚未登记文档。可以将现有的 Research Atlas Page 或 GitHub 技术规范作为权威原件加入索引。</div>}
            </div>
          </>}

          {!loading && section==="experiments" && <>
            {showForm&&<div className="ds-card ds-form">
              <h2>登记可追溯实验</h2><div className="ds-formgrid">
                <label>所属模块<select value={moduleId} onChange={e=>setModuleId(e.target.value)}>{Object.entries(moduleNames).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
                <label>实验名称<input value={experimentTitle} onChange={e=>setExperimentTitle(e.target.value)} placeholder="期刊官网与 OpenAlex 采集对照"/></label>
                <label className="full">假设与预期变化<textarea rows={3} value={experimentHypothesis} onChange={e=>setExperimentHypothesis(e.target.value)} placeholder="预期通过分页减少已知官网论文漏检。"/></label>
                <label>基线<input value={experimentBaseline} onChange={e=>setExperimentBaseline(e.target.value)} placeholder="旧版 100 条截断采集"/></label>
                <label>输入快照引用<input value={experimentInput} onChange={e=>setExperimentInput(e.target.value)} placeholder="experiments/.../benchmark.json"/></label>
              </div><div className="ds-formactions"><button className="ds-btn" onClick={()=>setShowForm(false)}>取消</button>
                <button disabled={busy} className="ds-btn ds-primary" onClick={()=>void submit(()=>api("devstudio/experiments",{method:"POST",body:JSON.stringify({
                  module_id:moduleId,title:experimentTitle,hypothesis:experimentHypothesis,baseline:experimentBaseline,input_snapshot_ref:experimentInput,
                })}),"实验已登记，接下来可绑定实际 GitHub Actions 运行。")}>登记实验</button></div>
            </div>}
            <div className="ds-search"><Search size={16}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="搜索实验、假设或模块"/></div>
            <div className="ds-split">
              <div className="ds-card ds-list">
                {visibleExperiments.length?visibleExperiments.map(x=><button key={x.id} className={"ds-listrow ds-rowbutton "+(x.id===selectedExperiment?.id?"selected":"")}
                  onClick={()=>void openExperiment(x)}>
                  <div><span className="ds-modulecode">{x.module_id}</span><strong>{x.title}</strong>
                    <p>{x.hypothesis}</p><small>{day(x.created_at)} · {label(x.status)}</small></div><ChevronRight size={17}/>
                </button>):<div className="ds-empty">当前还没有实验记录。先创建实验，再关联实际运行。</div>}
              </div>
              <div className="ds-card">
                {selectedExperiment?<><span className="ds-eyebrow">EXPERIMENT DETAIL</span><h2>{selectedExperiment.title}</h2>
                  <p>{selectedExperiment.hypothesis}</p>
                  <div className="ds-kv"><span>对照基线</span><strong>{selectedExperiment.baseline||"未填写"}</strong></div>
                  <div className="ds-kv"><span>输入快照</span><strong>{selectedExperiment.input_snapshot_ref||"未填写"}</strong></div>
                  <div className="ds-sectionhead"><h3>实际运行</h3><span>{runs.length} 条</span></div>
                  {runs.map(x=><div className="ds-run" key={x.id}>
                    <div><strong>{label(x.status)}</strong><small>{day(x.created_at)}</small></div>
                    {x.external_url.startsWith("https://")?<LinkExternal href={x.external_url}>GitHub Run</LinkExternal>:<span className="ds-subtle">{x.external_url}</span>}
                    <small>{x.note}</small>
                  </div>)}
                  {!runs.length&&<p className="ds-subtle">尚无绑定运行，不应推断本实验通过。</p>}
                  {canEdit&&<div className="ds-runform"><label>绑定真实 GitHub Actions Run<input value={runUrl} onChange={e=>setRunUrl(e.target.value)} placeholder="https://github.com/Hu-py/research-opportunity-workbench/actions/runs/…"/></label>
                    <button disabled={busy} className="ds-btn ds-primary" onClick={()=>void (async()=>{
                      setBusy(true);setError("");
                      try{await api("devstudio/experiments/"+selectedExperiment.id+"/runs",{method:"POST",body:JSON.stringify({kind:"github_actions",external_url:runUrl})});
                        setRunUrl("");await openExperiment(selectedExperiment);setNotice("已关联运行，状态保持未核验。");
                      }catch(e){setError(humanError(e));}finally{setBusy(false);}
                    })()}>关联运行</button></div>}
                </>:<div className="ds-empty">选择左侧实验，查看假设、输入快照与实际 Run。</div>}
              </div>
            </div>
          </>}

          {!loading && section==="changes" && <>
            <div className="ds-tabs">
              {["DISCOVERY","SIGNAL_L1","PLATFORM","TEAM_FIT"].map(id=><button key={id} className={moduleId===id?"ds-tab active":"ds-tab"}
                onClick={()=>void loadLineage(id)}>{moduleNames[id]}</button>)}
            </div>
            {showForm&&<div className="ds-card ds-form"><h2>提交技术变更</h2>
              <div className="ds-formgrid">
                <label>所属模块<select value={moduleId} onChange={e=>setModuleId(e.target.value)}>{Object.entries(moduleNames).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
                <label>变更标题<input value={changeTitle} onChange={e=>setChangeTitle(e.target.value)}/></label>
                <label className="full">修改原因和已有证据<textarea rows={4} value={changeReason} onChange={e=>setChangeReason(e.target.value)}/></label>
              </div><div className="ds-formactions"><button className="ds-btn" onClick={()=>setShowForm(false)}>取消</button>
                <button disabled={busy} className="ds-btn ds-primary" onClick={()=>void submit(()=>api("devstudio/changes",{method:"POST",body:JSON.stringify({
                  module_id:moduleId,kind:"code",title:changeTitle,reason:changeReason,proposed:{scope:"Technical change proposal; implementation requires GitHub PR"},
                })}),"技术变更提案已提交。")}>提交变更</button></div>
            </div>}
            <div className="ds-search"><Search size={16}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="搜索变更原因、类型和标题"/></div>
            <div className="ds-sectionhead"><h2>变更与审批队列</h2><span>{visibleChanges.length} 项 · 审批不代表发布</span></div>
            <div className="ds-card ds-list">
              {visibleChanges.length?visibleChanges.map(x=><div className="ds-listrow ds-changerow" key={x.id}>
                <div><span className="ds-modulecode">{x.kind.toUpperCase()} / {x.module_id} / 风险 {x.risk}</span>
                  <strong>{x.title}</strong><p><b>修改原因：</b>{x.reason}</p>
                  <small>{day(x.created_at)} · {x.id}</small>
                </div><div className="ds-changeactions"><span className="ds-pill">{label(x.status)}</span>
                  {canApprove&&x.status==="submitted"&&<div className="ds-actionbuttons">
                    <button className="ds-btn ds-approve" disabled={busy||x.created_by===session?.member?.id} title="仅其他管理员可审批"
                      onClick={()=>void decide(x,"approve")}>批准</button>
                    <button className="ds-btn" disabled={busy||x.created_by===session?.member?.id}
                      onClick={()=>void decide(x,"request_changes")}>退回</button>
                    <button className="ds-btn" disabled={busy||x.created_by===session?.member?.id}
                      onClick={()=>void decide(x,"reject")}>拒绝</button>
                  </div>}
                </div>
              </div>):<div className="ds-empty">尚未登记变更请求。新增期刊等维护申请也会出现在这里。</div>}
            </div>
            <div className="ds-sectionhead"><h2>当前模块版本与决策线索</h2>
              <button className="ds-btn" onClick={()=>void loadLineage(moduleId)}><RefreshCw size={14}/>查看已登记关联</button></div>
            {lineage&&<div className="ds-card">
              <p className="ds-subtle">仅展示显式关联的记录。时间相邻不代表因果关系；不从 GitHub CI 自动推断正式部署。</p>
              <div className="ds-lineage">
                {lineage.issues.map(x=><div key={x.id}><span>问题</span><strong>{x.title}</strong><small>{day(x.created_at)}</small></div>)}
                {lineage.changes.map(x=><div key={x.id}><span>变更</span><strong>{x.title}</strong><small>{label(x.status)}</small></div>)}
                {lineage.experiments.map(x=><div key={x.id}><span>实验</span><strong>{x.title}</strong><small>{label(x.status)}</small></div>)}
                {lineage.runs.map(x=><div key={x.id}><span>运行</span><strong>{x.external_url}</strong><small>{label(x.status)}</small></div>)}
                {lineage.decisions.map(x=><div key={x.id}><span>审批</span><strong>{x.reason}</strong><small>{x.decision}</small></div>)}
                {!lineage.issues.length&&!lineage.changes.length&&!lineage.experiments.length&&
                  <div className="ds-empty">当前模块还没有可追溯的研发事件。</div>}
              </div>
            </div>}
            {canEdit&&<div className="ds-card ds-form">
              <h3>登记新的研发问题</h3>
              <div className="ds-formgrid"><label>问题标题<input value={issueTitle} onChange={e=>setIssueTitle(e.target.value)}/></label>
                <label>所属模块<select value={moduleId} onChange={e=>setModuleId(e.target.value)}>{Object.entries(moduleNames).map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label>
                <label className="full">问题描述与证据<textarea value={issueDescription} onChange={e=>setIssueDescription(e.target.value)} rows={3}/></label></div>
              <div className="ds-formactions"><button className="ds-btn ds-primary" disabled={busy} onClick={()=>void submit(()=>api("devstudio/issues",{method:"POST",body:JSON.stringify({
                module_id:moduleId,title:issueTitle,description:issueDescription
              })}),"研发问题已登记；可在后续变更中引用。")}>登记问题</button></div>
            </div>}
          </>}
          <footer className="ds-footer">
            <span>Research Atlas Development Studio · P0</span>
            <span>所有审批、来源配置和实验状态均以真实后端记录为准</span>
          </footer>
        </>}
      </div>
    </main>
  </div>;
}
