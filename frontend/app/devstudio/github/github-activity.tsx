"use client";
import Link from "next/link";
import {useCallback,useEffect,useMemo,useState} from "react";
import styles from "./github-activity.module.css";

type Activity = {
  event_key:string;kind:string;title:string;url:string;status:string;
  actor:string;branch:string;sha:string;detail:string;
  source_updated_at:string;received_at:string;
};
type Feed = {
  repo:string;items:Activity[];integration_status:string;
  public_poll?:{state:string;events?:number;error?:string;last_success?:string|null};
  last_received_at:string|null;note:string;
};
const names:Record<string,string> = {
  push:"代码提交",pull_request:"Pull Request",issue:"Issue",workflow_run:"CI 运行",
};
const states:Record<string,string> = {
  recorded:"已记录",draft:"草稿",open:"开放",closed:"关闭",merged:"已合并",
  success:"CI 通过",failure:"CI 失败",in_progress:"进行中",queued:"排队中",
  cancelled:"取消",skipped:"跳过",neutral:"中性",
};
function day(raw:string|null|undefined) {
  if(!raw)return "未知";
  const stamp=new Date(raw);
  return Number.isNaN(stamp.getTime())?raw.slice(0,19):
    stamp.toLocaleString("zh-CN",{timeZone:"Asia/Shanghai",hour12:false});
}
export default function GithubActivity() {
  const [feed,setFeed]=useState<Feed|null>(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [filter,setFilter]=useState("all");
  const load=useCallback(async()=>{
    setBusy(true);
    try {
      const res=await fetch("/api/proxy/devstudio/github/activity",{
        cache:"no-store",credentials:"same-origin",
      });
      if(!res.ok)throw Error("后端未连接或团队登录失效（HTTP "+res.status+"）");
      setFeed(await res.json() as Feed);
      setError("");
    }catch(e){setError(e instanceof Error?e.message:"读取失败");}
    finally{setBusy(false);}
  },[]);
  useEffect(()=>{
    void load();
    const handle=setInterval(()=>{void load();},60000);
    return()=>clearInterval(handle);
  },[load]);
  const items=useMemo(()=>feed?.items.filter(x=>filter==="all"||x.kind===filter)||[],[feed,filter]);
  const sync=feed?.public_poll;
  return <main className={styles.root}>
    <div className={styles.shell}>
      <div className={styles.top}>
        <Link href="/devstudio">← 返回开发者平台</Link>
        <Link href="/devstudio/experiments">实验与评测</Link>
      </div>
      <header className={styles.heading}>
        <div><span className={styles.eyebrow}>RESEARCH ATLAS / DEVELOPMENT STUDIO</span>
          <h1>GitHub 研发动态</h1>
          <p>自动同步提交、PR、Issue 与 CI。工程状态与科研评审分别记录，不自动批准实验。</p></div>
        <button type="button" onClick={()=>void load()} disabled={busy}>{busy?"正在读取":"刷新动态"}</button>
      </header>
      <div className={styles.summary}>
        <div><small>已记录事件</small><strong>{feed?.items.length??"—"}</strong></div>
        <div><small>同步模式</small><strong>{sync?.state==="disabled"?"待启用":sync?.state==="error"?"同步异常":
          sync?.state==="cached"?"缓存更新":"已更新"}</strong></div>
        <div><small>最近同步</small><strong className={styles.date}>{day(sync?.last_success||feed?.last_received_at)}</strong></div>
      </div>
      {error&&<div className={styles.error} role="alert">{error}</div>}
      {sync?.state==="error"&&<div className={styles.error} role="status">
        GitHub 暂时不可读取（{sync.error||"unknown"}），已保存的历史记录仍可查看。
      </div>}
      <div className={styles.toolbar}>
        <span>仓库：{feed?.repo||"Hu-py/research-opportunity-workbench"}</span>
        <select value={filter} onChange={e=>setFilter(e.target.value)} aria-label="筛选 GitHub 事件">
          <option value="all">所有动态</option>
          <option value="pull_request">PR 变更</option>
          <option value="push">代码提交</option>
          <option value="issue">Issue</option>
          <option value="workflow_run">CI 运行</option>
        </select>
      </div>
      <div className={styles.tablewrap}>
        <table>
          <thead><tr><th>类型</th><th>事件</th><th>状态</th><th>人员 / 分支</th><th>更新</th></tr></thead>
          <tbody>{items.map(x=><tr key={x.event_key}>
            <td>{names[x.kind]||x.kind}</td>
            <td><a href={x.url} target="_blank" rel="noopener noreferrer">{x.title} ↗</a>
              <small>{x.detail}</small></td>
            <td><span className={styles.status}>{states[x.status]||x.status}</span></td>
            <td>{x.actor||"GitHub"}<small>{x.branch}</small></td>
            <td>{day(x.source_updated_at||x.received_at)}</td>
          </tr>)}</tbody>
        </table>
        {!busy&&!items.length&&<p className={styles.empty}>尚无相应记录。测试后端需启用公开 GitHub 同步，才能自动拉取近期活动。</p>}
      </div>
      <footer className={styles.note}>
        这里显示的是 GitHub 公开仓库的近期研发事件，不是全部历史 commit。
        成功构建不等于已部署，更不等于科研结论通过。当前不会自动建立实验记录、审批或科学评测。
      </footer>
    </div>
  </main>;
}
