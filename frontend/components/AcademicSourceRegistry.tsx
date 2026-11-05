"use client";

import {useCallback,useEffect,useMemo,useState} from "react";
import {
  BookMarked,CheckCircle2,Download,FileUp,Filter,Globe2,History,
  Plus,RefreshCw,Search,ShieldCheck,X
} from "lucide-react";
import {api} from "@/lib/api";

type Domain={
  slug:string;name:string;group_name:string;description:string;
  default_channels:string[];sort_order:number;enabled:boolean;is_seed:boolean;
};
type Source={
  id:string;name:string;abbreviation:string;kind:"journal"|"conference";
  domains:string[];rank_label:string;ranking_system:string;ranking_version:string;
  ranking_source_url:string;source_url:string;aliases:string[];notes:string;retrieval_channels:("direct"|"method")[];
  enabled:boolean;is_seed:boolean;openalex_source_id:string;
  resolution_status:"unresolved"|"resolved"|"ambiguous"|"not_found"|"error";
  openalex_type:string;resolution_note:string;updated_at:string|null;
};
type Summary={
  total:number;enabled:number;disabled:number;resolved:number;unresolved:number;
  ambiguous:number;not_found:number;errors:number;
  journals:number;conferences:number;domains:number;direct_enabled:number;method_enabled:number;
};
type Registry={
  items:Source[];domains:Domain[];summary:Summary;
  catalogue:{catalogue_version:string;last_seeded_at:string|null};note:string;
};
type Revision={
  id:string;action:string;actor_id:string;created_at:string;
  before:Record<string,unknown>;after:Record<string,unknown>;
};
type Form={
  name:string;abbreviation:string;kind:"journal"|"conference";domains:string[];
  rank_label:string;ranking_system:string;ranking_version:string;ranking_source_url:string;source_url:string;
  aliases:string;notes:string;retrieval_channels:("direct"|"method")[];
  enabled:boolean;openalex_source_id:string;
};
const blankForm:Form={
  name:"",abbreviation:"",kind:"journal",domains:[],rank_label:"重点",
  ranking_system:"团队自定义遴选",ranking_version:"",ranking_source_url:"",source_url:"",
  aliases:"",notes:"",retrieval_channels:["direct"],enabled:true,openalex_source_id:"",
};
const statusText:Record<string,string>={
  resolved:"已核验",unresolved:"待核验",ambiguous:"多项匹配",
  not_found:"未找到",error:"核验失败",
};
function split(value:string){return Array.from(new Set(value.split(/[\n,，;；|]+/).map(x=>x.trim()).filter(Boolean)));}
function badgeStatus(status:string){
  return status==="resolved"?"registry-status-ok":
    status==="ambiguous"?"registry-status-warn":
    status==="error"||status==="not_found"?"registry-status-bad":"registry-status-pending";
}
function asForm(item:Source):Form{
  return {
    name:item.name,abbreviation:item.abbreviation,kind:item.kind,domains:item.domains,
    rank_label:item.rank_label,ranking_system:item.ranking_system,
    ranking_version:item.ranking_version,ranking_source_url:item.ranking_source_url,source_url:item.source_url,
    aliases:item.aliases.join("\n"),notes:item.notes,
    retrieval_channels:item.retrieval_channels,enabled:item.enabled,
    openalex_source_id:item.openalex_source_id||"",
  };
}
export default function AcademicSourceRegistry({canEdit,canAdmin}:{
  canEdit:boolean;canAdmin:boolean;
}){
  const [data,setData]=useState<Registry|null>(null);
  const [query,setQuery]=useState("");
  const [kind,setKind]=useState("all");
  const [domain,setDomain]=useState("all");
  const [channel,setChannel]=useState("all");
  const [status,setStatus]=useState("all");
  const [enabled,setEnabled]=useState("all");
  const [editing,setEditing]=useState<string|null>(null);
  const [form,setForm]=useState<Form>(blankForm);
  const [formOpen,setFormOpen]=useState(false);
  const [domainOpen,setDomainOpen]=useState(false);
  const [editingDomain,setEditingDomain]=useState<string|null>(null);
  const [domainEnabled,setDomainEnabled]=useState(true);
  const [domainName,setDomainName]=useState("");
  const [domainSlug,setDomainSlug]=useState("");
  const [domainGroup,setDomainGroup]=useState("计算机前沿");
  const [domainDescription,setDomainDescription]=useState("");
  const [domainChannels,setDomainChannels]=useState<("direct"|"method")[]>(["method"]);
  const [historyId,setHistoryId]=useState("");
  const [history,setHistory]=useState<Revision[]>([]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [notice,setNotice]=useState("");
  const [resolveResult,setResolveResult]=useState<Record<string,unknown>|null>(null);

  const load=useCallback(async()=>{
    const result=await api<Registry>("academic-sources");
    setData(result);
  },[]);
  useEffect(()=>{void load().catch(e=>setError(e instanceof Error?e.message:"学术来源目录读取失败"));},[load]);

  const visible=useMemo(()=>{
    const items=data?.items||[];
    const q=query.trim().toLocaleLowerCase();
    return items.filter(x=>{
      if(kind!=="all"&&x.kind!==kind)return false;
      if(domain!=="all"&&!x.domains.includes(domain))return false;
      if(channel!=="all"&&!x.retrieval_channels.includes(channel as "direct"|"method"))return false;
      if(status!=="all"&&x.resolution_status!==status)return false;
      if(enabled==="on"&&!x.enabled)return false;
      if(enabled==="off"&&x.enabled)return false;
      if(q&&![
        x.name,x.abbreviation,x.notes,x.rank_label,x.ranking_system,
        ...x.aliases,...x.domains
      ].join(" ").toLocaleLowerCase().includes(q))return false;
      return true;
    });
  },[data,query,kind,domain,channel,status,enabled]);

  function openCreate(){
    setEditing(null);setForm({...blankForm,domains:data?.domains.filter(x=>x.enabled).slice(0,1).map(x=>x.slug)||[]});
    setFormOpen(true);setError("");setNotice("");
  }
  function openEdit(item:Source){
    setEditing(item.id);setForm(asForm(item));setFormOpen(true);setError("");setNotice("");
  }
  function patchForm<K extends keyof Form>(key:K,value:Form[K]){
    setForm(prev=>({...prev,[key]:value}));
  }
  async function saveSource(){
    setBusy(true);setError("");setNotice("");
    const payload={
      ...form,aliases:split(form.aliases),openalex_source_id:form.openalex_source_id.trim(),
    };
    try{
      if(editing){
        await api<Source>("academic-sources/"+encodeURIComponent(editing),{
          method:"PATCH",body:JSON.stringify(payload),
        });
        setNotice("来源信息已更新，修改前后快照已写入变更历史。");
      }else{
        await api<Source>("academic-sources",{
          method:"POST",body:JSON.stringify(payload),
        });
        setNotice("新学术来源已加入目录。");
      }
      setFormOpen(false);setEditing(null);await load();
    }catch(e){setError(e instanceof Error?e.message:"保存失败");}
    finally{setBusy(false);}
  }
  async function toggleSource(item:Source){
    setBusy(true);setError("");setNotice("");
    try{
      await api<Source>("academic-sources/"+encodeURIComponent(item.id),{
        method:"PATCH",body:JSON.stringify({enabled:!item.enabled}),
      });
      setNotice(item.enabled?"来源已暂停，不再参与新一轮检索。":"来源已恢复，可参与后续检索。");
      await load();
    }catch(e){setError(e instanceof Error?e.message:"更新失败");}
    finally{setBusy(false);}
  }
  async function resolveBatch(){
    setBusy(true);setError("");setNotice("");setResolveResult(null);
    try{
      const result=await api<Record<string,unknown>>("academic-sources/resolve",{
        method:"POST",body:JSON.stringify({max_items:10,force:false}),
      });
      setResolveResult(result);
      const checked=Number(result.checked||0),resolved=Number(result.resolved||0);
      setNotice(checked?("本批核验 "+checked+" 个来源，成功匹配 "+resolved+" 个。"):"没有待核验来源；多项匹配或失败项可在对应来源卡片中单独重试。");
      await load();
    }catch(e){setError(e instanceof Error?e.message:"来源核验失败");}
    finally{setBusy(false);}
  }
  async function resolveOne(item:Source){
    setBusy(true);setError("");setNotice("");
    try{
      const result=await api<Record<string,unknown>>("academic-sources/resolve",{
        method:"POST",body:JSON.stringify({source_ids:[item.id],max_items:1,force:true}),
      });
      const first=(result.items as {status?:string;note?:string}[]|undefined)?.[0];
      setNotice(item.name+"："+(first?.note||first?.status||"核验完成"));
      await load();
    }catch(e){setError(e instanceof Error?e.message:"来源核验失败");}
    finally{setBusy(false);}
  }
  async function exportCsv(){
    setBusy(true);setError("");
    try{
      const result=await api<{filename:string;content:string}>("academic-sources/export");
      const blob=new Blob(["\ufeff",result.content],{type:"text/csv;charset=utf-8"});
      const url=URL.createObjectURL(blob);
      const link=document.createElement("a");link.href=url;link.download=result.filename;link.click();
      URL.revokeObjectURL(url);setNotice("已导出当前目录，可用于版本备份或批量编辑。");
    }catch(e){setError(e instanceof Error?e.message:"导出失败");}
    finally{setBusy(false);}
  }
  async function importCsv(file?:File){
    if(!file)return;
    setBusy(true);setError("");setNotice("");
    try{
      const csv_text=await file.text();
      const result=await api<{created:number;updated:number;skipped:number;errors:{row:number;name?:string;error:string}[]}>(
        "academic-sources/import",{method:"POST",body:JSON.stringify({csv_text})});
      setNotice("导入完成：新增 "+result.created+"，更新 "+result.updated+"，跳过 "+result.skipped+"，错误 "+result.errors.length+"。");
      if(result.errors.length)setError(result.errors.slice(0,5).map(x=>"第"+x.row+"行 "+(x.name||"")+x.error).join("；"));
      await load();
    }catch(e){setError(e instanceof Error?e.message:"CSV 导入失败");}
    finally{setBusy(false);}
  }
  async function showHistory(item:Source){
    setHistoryId(item.id);setHistory([]);
    try{
      const result=await api<{items:Revision[]}>("academic-sources/"+encodeURIComponent(item.id)+"/history");
      setHistory(result.items);
    }catch(e){setError(e instanceof Error?e.message:"读取变更历史失败");}
  }
  function openNewDomain(){
    setEditingDomain(null);setDomainEnabled(true);setDomainName("");setDomainSlug("");
    setDomainGroup("计算机前沿");setDomainDescription("");setDomainChannels(["method"]);setDomainOpen(true);
  }
  function openEditDomain(item:Domain){
    setEditingDomain(item.slug);setDomainEnabled(item.enabled);setDomainName(item.name);
    setDomainSlug(item.slug);setDomainGroup(item.group_name);setDomainDescription(item.description);
    setDomainChannels(item.default_channels as ("direct"|"method")[]);setDomainOpen(true);
  }
  async function saveDomain(){
    setBusy(true);setError("");setNotice("");
    try{
      const payload={name:domainName.trim(),group_name:domainGroup,
        description:domainDescription,default_channels:domainChannels,enabled:domainEnabled};
      if(editingDomain){
        await api<Domain>("academic-domains/"+encodeURIComponent(editingDomain),{
          method:"PATCH",body:JSON.stringify(payload),
        });
        setNotice("研究领域信息已更新。");
      }else{
        await api<Domain>("academic-domains",{method:"POST",body:JSON.stringify({
          ...payload,slug:domainSlug.trim().toLowerCase().replace(/[\s-]+/g,"_"),
        })});
        setNotice("研究领域已添加，之后可直接分配给期刊和会议。");
      }
      setDomainOpen(false);setEditingDomain(null);await load();
    }catch(e){setError(e instanceof Error?e.message:"领域保存失败");}
    finally{setBusy(false);}
  }

  return <div className="academic-registry">
    <div className="page-heading">
      <span className="panel-kicker">ACADEMIC SOURCE REGISTRY</span>
      <h1>学术来源管理</h1>
      <p>统一管理团队关注的期刊、会议、学科分类与检索范围。数据库是运行时主数据，GitHub 中的 JSON 目录仅作为可追溯的初始配置。</p>
    </div>
    {error&&<div className="alert alert-error"><span>{error}</span><button onClick={()=>setError("")}><X size={14}/></button></div>}
    {notice&&<div className="alert alert-success"><CheckCircle2 size={15}/><span>{notice}</span><button onClick={()=>setNotice("")}><X size={14}/></button></div>}
    <div className="repository-stat-row academic-registry-stats">
      <div><strong>{data?.summary.total??"—"}</strong><span>学术来源</span></div>
      <div><strong>{data?.summary.enabled??"—"}</strong><span>已启用</span></div>
      <div><strong>{data?.summary.resolved??"—"}</strong><span>OpenAlex 已核验</span></div>
      <div><strong>{data?.summary.domains??"—"}</strong><span>研究领域</span></div>
    </div>

    <section className="panel academic-registry-intro">
      <div className="panel-header">
        <div><span className="panel-kicker">REGISTRY GOVERNANCE</span><h2>目录治理与更新方式</h2></div>
        <ShieldCheck size={21}/>
      </div>
      <div className="academic-governance-grid">
        <div><strong>配置版本</strong><span>{data?.catalogue.catalogue_version||"等待初始化"}</span></div>
        <div><strong>来源类型</strong><span>{data?.summary.journals??0} 种期刊 · {data?.summary.conferences??0} 个会议</span></div>
        <div><strong>检索通道</strong><span>直接问题 {data?.summary.direct_enabled??0} · 方法迁移 {data?.summary.method_enabled??0}</span></div>
      </div>
      <p className="small muted">CCF 等级、规划学科遴选标签和团队自定义等级分别记录，不强行换算。会议等级不等于单篇论文等级；Short Paper、Workshop、Demo 等类型仍需单独核验。</p>
    </section>

    <div className="academic-registry-toolbar">
      <div className="academic-registry-search"><Search size={17}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="搜索期刊、会议、简称、别名或关键词"/></div>
      <div className="inline-actions">
        <button className="btn" disabled={busy} onClick={()=>void load()}><RefreshCw size={14}/>刷新</button>
        <button className="btn" disabled={busy} onClick={()=>void exportCsv()}><Download size={14}/>导出 CSV</button>
        {canAdmin&&<label className="btn academic-file-button"><FileUp size={14}/>导入 CSV<input type="file" accept=".csv,text/csv" disabled={busy} onChange={e=>{void importCsv(e.target.files?.[0]);e.currentTarget.value="";}}/></label>}
        {canEdit&&<button className="btn btn-primary" onClick={openCreate}><Plus size={14}/>新增来源</button>}
      </div>
    </div>

    <section className="panel academic-filter-panel">
      <div className="academic-filter-heading"><Filter size={15}/><strong>筛选目录</strong><span>{visible.length} / {data?.items.length??0} 项</span></div>
      <div className="academic-filter-grid">
        <label>来源类型<select value={kind} onChange={e=>setKind(e.target.value)}><option value="all">全部类型</option><option value="journal">期刊</option><option value="conference">会议</option></select></label>
        <label>研究领域<select value={domain} onChange={e=>setDomain(e.target.value)}><option value="all">全部领域</option>{(data?.domains||[]).filter(x=>x.enabled).map(x=><option key={x.slug} value={x.slug}>{x.name}</option>)}</select></label>
        <label>检索通道<select value={channel} onChange={e=>setChannel(e.target.value)}><option value="all">全部通道</option><option value="direct">研究问题检索</option><option value="method">方法迁移检索</option></select></label>
        <label>核验状态<select value={status} onChange={e=>setStatus(e.target.value)}><option value="all">全部状态</option><option value="resolved">已核验</option><option value="unresolved">待核验</option><option value="ambiguous">多项匹配</option><option value="not_found">未找到</option><option value="error">核验失败</option></select></label>
        <label>启用状态<select value={enabled} onChange={e=>setEnabled(e.target.value)}><option value="all">全部</option><option value="on">已启用</option><option value="off">已暂停</option></select></label>
      </div>
    </section>

    <section className="academic-source-list">
      {!data?<div className="panel"><p className="small muted">正在读取学术来源目录…</p></div>:
        visible.length===0?<div className="panel academic-empty"><BookMarked size={26}/><strong>没有匹配的学术来源</strong><p>调整筛选条件，或新增期刊和会议。</p></div>:
        visible.map(item=><article className={"panel academic-source-card "+(!item.enabled?"academic-source-disabled":"")} key={item.id}>
          <div className="academic-source-main">
            <div className="academic-source-title">
              <div><span className="academic-kind">{item.kind==="journal"?"JOURNAL":"CONFERENCE"}</span>
                {item.is_seed&&<span className="academic-seed">初始目录</span>}
                <h3>{item.name}</h3>
                <p>{item.abbreviation||"暂无简称"}{item.source_url&&<> · <a href={item.source_url} target="_blank" rel="noopener noreferrer">官方主页 ↗</a></>}</p>
              </div>
              <span className={"registry-status "+badgeStatus(item.resolution_status)}>{statusText[item.resolution_status]||item.resolution_status}</span>
            </div>
            <div className="academic-source-meta">
              <span className="academic-rank">{item.rank_label}</span>
              <span>{item.ranking_system||"团队自定义来源"}</span>
              {item.ranking_version&&<span>{item.ranking_version}</span>}
              {item.ranking_source_url&&<a href={item.ranking_source_url} target="_blank" rel="noopener noreferrer">等级依据 ↗</a>}
            </div>
            <div className="academic-source-tags">
              {item.domains.map(slug=><span key={slug}>{data.domains.find(x=>x.slug===slug)?.name||slug}</span>)}
              {item.retrieval_channels.map(x=><span className="academic-channel" key={x}>{x==="direct"?"研究问题":"方法迁移"}</span>)}
            </div>
            {item.notes&&<p className="academic-source-notes">{item.notes}</p>}
            <div className="academic-source-footer">
              <span>{item.openalex_source_id?"OpenAlex "+item.openalex_source_id:item.resolution_note||"尚未关联 OpenAlex Source ID"}</span>
              <div className="inline-actions">
                <button className="text-link" onClick={()=>void showHistory(item)}><History size={13}/>变更记录</button>
                {canEdit&&item.enabled&&item.resolution_status!=="resolved"&&<button className="text-link" disabled={busy} onClick={()=>void resolveOne(item)}>重新核验</button>}
                {canEdit&&<button className="text-link" onClick={()=>openEdit(item)}>编辑</button>}
                {canEdit&&<button className="btn btn-secondary" disabled={busy} onClick={()=>void toggleSource(item)}>{item.enabled?"暂停检索":"恢复检索"}</button>}
              </div>
            </div>
          </div>
        </article>)}
    </section>

    <section className="panel academic-resolution-panel">
      <div className="panel-header"><div><span className="panel-kicker">OPENALEX SOURCE RESOLUTION</span><h2>来源 ID 核验</h2></div><Globe2 size={21}/></div>
      <p className="small muted">系统仅在期刊/会议名称、简称或别名与 OpenAlex 来源名称精确匹配时自动确认。存在多个匹配项时保留人工处理，不猜测 ID。</p>
      <div className="academic-resolution-actions">
        <div><strong>待核验 {data?.summary.unresolved??"—"} 个</strong><span>每批处理 10 个来源；多项匹配或失败项可单独重试。</span></div>
        <div className="inline-actions">
          <button className="btn btn-primary" disabled={busy||!canEdit||!data?.summary.unresolved} onClick={()=>void resolveBatch()}><RefreshCw size={14}/>核验下一批</button>
        </div>
      </div>
      {resolveResult&&<pre className="academic-resolve-result">{JSON.stringify(resolveResult,null,2)}</pre>}
    </section>

    {canAdmin&&<section className="panel academic-domain-panel">
      <div className="panel-header"><div><span className="panel-kicker">TAXONOMY</span><h2>研究领域分类</h2></div>
        <button className="btn" onClick={openNewDomain}><Plus size={14}/>新增领域</button>
      </div>
      <p className="small muted">领域分类保存在数据库中，不需要修改代码即可扩充。来源可同时归入多个领域。</p>
      <div className="academic-domain-grid">{(data?.domains||[]).map(x=><div className={"academic-domain-chip "+(!x.enabled?"is-disabled":"")} key={x.slug}>
        <strong>{x.name}</strong><span>{x.group_name||x.slug} · {x.slug}</span><small>{x.description}</small>
        <button className="text-link" onClick={()=>openEditDomain(x)}>编辑领域</button>
      </div>)}</div>
      {domainOpen&&<div className="academic-domain-form">
        <strong>{editingDomain?"编辑研究领域":"新增研究领域"}</strong>
        <div className="feedback-grid">
          <label>领域名称<input value={domainName} onChange={e=>setDomainName(e.target.value)} placeholder="例如：数字孪生与仿真"/></label>
          {!editingDomain&&<label>领域标识<input value={domainSlug} onChange={e=>setDomainSlug(e.target.value)} placeholder="digital_twin"/></label>}
          <label>所属分组<input value={domainGroup} onChange={e=>setDomainGroup(e.target.value)}/></label>
        </div>
        <label>领域说明<textarea rows={2} value={domainDescription} onChange={e=>setDomainDescription(e.target.value)}/></label>
        <label className="academic-enabled-check"><input type="checkbox" checked={domainEnabled} onChange={e=>setDomainEnabled(e.target.checked)}/>启用该领域</label>
        <div className="academic-channel-checks">
          <strong>默认检索通道</strong>
          {(["direct","method"] as const).map(x=><label key={x}><input type="checkbox" checked={domainChannels.includes(x)} onChange={e=>setDomainChannels(prev=>e.target.checked?[...prev,x]:prev.filter(y=>y!==x))}/>{x==="direct"?"研究问题检索":"方法迁移检索"}</label>)}
        </div>
        <div className="inline-actions"><button className="btn btn-primary" disabled={busy||domainName.trim().length<2||(!editingDomain&&domainSlug.trim().length<2)} onClick={()=>void saveDomain()}>保存领域</button>
          <button className="btn" onClick={()=>setDomainOpen(false)}>取消</button></div>
      </div>}
    </section>}

    {formOpen&&<div className="academic-modal-backdrop" role="presentation" onClick={()=>setFormOpen(false)}>
      <section className="panel academic-source-editor" role="dialog" aria-modal="true" aria-label="编辑学术来源" onClick={e=>e.stopPropagation()}>
        <div className="panel-header"><div><span className="panel-kicker">SOURCE METADATA</span><h2>{editing?"编辑学术来源":"新增学术来源"}</h2></div>
          <button className="icon-only" onClick={()=>setFormOpen(false)} aria-label="关闭"><X size={18}/></button></div>
        <div className="academic-form-grid">
          <label className="span-2">期刊 / 会议全称<input value={form.name} onChange={e=>patchForm("name",e.target.value)} placeholder="正式出版名称"/></label>
          <label>简称<input value={form.abbreviation} onChange={e=>patchForm("abbreviation",e.target.value)} placeholder="例如 SIGSPATIAL"/></label>
          <label>来源类型<select value={form.kind} onChange={e=>patchForm("kind",e.target.value as Form["kind"])}><option value="journal">期刊</option><option value="conference">会议</option></select></label>
          <label>来源等级<input value={form.rank_label} onChange={e=>patchForm("rank_label",e.target.value)} placeholder="A / B / C / 核心 / 重点 / 观察"/></label>
          <label>等级版本<input value={form.ranking_version} onChange={e=>patchForm("ranking_version",e.target.value)} placeholder="例如 CCF 2026 第七版"/></label>
          <label className="span-2">等级依据<input value={form.ranking_system} onChange={e=>patchForm("ranking_system",e.target.value)} placeholder="官方目录名称或团队遴选依据"/></label>
          <label className="span-2">等级依据原始链接<input value={form.ranking_source_url} onChange={e=>patchForm("ranking_source_url",e.target.value)} placeholder="例如 CCF 官方目录 HTTPS 链接"/></label>
          <label className="span-2">官方主页<input value={form.source_url} onChange={e=>patchForm("source_url",e.target.value)} placeholder="https://..."/></label>
          <label className="span-2">研究领域（可多选）
            <select multiple size={5} value={form.domains} onChange={e=>{
              const selected=Array.from(e.target.selectedOptions).map(x=>x.value);
              patchForm("domains",selected);
              if(!editing){
                const defaults=(data?.domains||[]).filter(x=>selected.includes(x.slug))
                  .flatMap(x=>x.default_channels);
                patchForm("retrieval_channels",Array.from(new Set(defaults)) as ("direct"|"method")[]);
              }
            }}>
              {(data?.domains||[]).filter(x=>x.enabled||form.domains.includes(x.slug)).map(x=><option key={x.slug} value={x.slug}>{x.name} · {x.group_name}{x.enabled?"":"（已停用）"}</option>)}
            </select>
          </label>
          <label className="span-2">检索通道
            <div className="academic-channel-checks">
              {(["direct","method"] as const).map(x=><label key={x}><input type="checkbox" checked={form.retrieval_channels.includes(x)} onChange={e=>patchForm("retrieval_channels",e.target.checked?[...form.retrieval_channels,x]:form.retrieval_channels.filter(y=>y!==x))}/>{x==="direct"?"研究问题检索":"方法迁移检索"}</label>)}
            </div>
          </label>
          <label className="span-2">名称别名（每行一项）<textarea rows={3} value={form.aliases} onChange={e=>patchForm("aliases",e.target.value)} placeholder={"会议简称\nProceedings of ...\n其他出版名称"}/></label>
          <label className="span-2">备注与关注主题<textarea rows={3} value={form.notes} onChange={e=>patchForm("notes",e.target.value)}/></label>
          <label className="span-2">OpenAlex Source ID<input value={form.openalex_source_id} onChange={e=>patchForm("openalex_source_id",e.target.value)} placeholder="S123456 或 https://openalex.org/S123456"/></label>
        </div>
        <label className="academic-enabled-check"><input type="checkbox" checked={form.enabled} onChange={e=>patchForm("enabled",e.target.checked)}/>启用该来源，纳入后续文献检索</label>
        <div className="inline-actions"><button className="btn btn-primary" disabled={busy||form.name.trim().length<3||form.domains.length===0} onClick={()=>void saveSource()}><CheckCircle2 size={15}/>保存来源</button>
          <button className="btn" onClick={()=>setFormOpen(false)}>取消</button></div>
      </section>
    </div>}

    {historyId&&<div className="academic-modal-backdrop" role="presentation" onClick={()=>setHistoryId("")}>
      <section className="panel academic-history-panel" role="dialog" aria-modal="true" onClick={e=>e.stopPropagation()}>
        <div className="panel-header"><div><span className="panel-kicker">CHANGE HISTORY</span><h2>来源变更记录</h2></div>
          <button className="icon-only" onClick={()=>setHistoryId("")} aria-label="关闭"><X size={18}/></button></div>
        {!history.length?<p className="small muted">暂无变更记录，或正在读取。</p>:history.map(x=><article className="academic-history-item" key={x.id}>
          <strong>{x.action==="created"?"创建":x.action==="resolved"?"来源核验":"信息更新"}</strong>
          <span>{x.created_at?new Date(x.created_at).toLocaleString("zh-CN"):"时间未记录"} · {x.actor_id||"系统"}</span>
          {x.before.name&&<small>修改前：{String(x.before.name)} · {String(x.before.rank_label||"")}</small>}
          {x.after.name&&<small>修改后：{String(x.after.name)} · {String(x.after.rank_label||"")} · {String(x.after.resolution_status||"")}</small>}
        </article>)}
      </section>
    </div>}
  </div>;
}
