"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle, ArrowUpRight, BookOpen, Check,
  CheckCircle2, ChevronDown, ChevronRight, Download, FileText,
  Loader2, LogOut, Menu, MessageCircle, Plus, RefreshCw, Search, Send,
  Settings2, ShieldCheck, UserRound, Users, X,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Profile, ResearchLine, Task, TeamAudit, TeamMember } from "@/lib/types";
import AcademicSourceRegistry from "@/components/AcademicSourceRegistry";
import InterestWatchlist from "@/components/InterestWatchlist";
import styles from "./ResearchAtlasV1.module.css";

type Section = "chat" | "team-weekly" | "personal-weekly" | "tasks" | "settings";
type SettingsTab = "profile" | "sources" | "interests" | "members";
type ChatScope = "private" | "team";

const emptyProfile: Profile = {
  goals: "",
  team: { name: "", mission: "", priorities: [] },
  datasets: [],
  methods: [],
  excluded_terms: [],
  research_lines: [],
};

const sectionNames: Record<Section, string> = {
  chat: "对话",
  "team-weekly": "团队周报",
  "personal-weekly": "个人周报",
  tasks: "定向科研任务",
  settings: "研究设置",
};

function dateTime(value?: string) {
  if (!value) return "时间未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

function shortDate(value?: string) {
  if (!value) return "尚无记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
}

function statusText(status: Task["status"]) {
  return ({ queued: "排队中", running: "执行中", completed: "已完成", failed: "执行失败" })[status];
}

function Status({ status }: { status: Task["status"] }) {
  const className = status === "completed" ? styles.statusDone
    : status === "failed" ? styles.statusFailed
    : status === "running" ? styles.statusRunning : styles.statusQueued;
  return <span className={styles.status + " " + className}>{statusText(status)}</span>;
}

function PageHeader({ eyebrow, title, description, action }: {
  eyebrow: string; title: string; description: string; action?: React.ReactNode;
}) {
  return (
    <div className={styles.pageHeader}>
      <div>
        <div className={styles.eyebrow}>{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action && <div className={styles.headerAction}>{action}</div>}
    </div>
  );
}

function ReportBody({ markdown }: { markdown: string }) {
  if (!markdown.trim()) {
    return <div className={styles.emptyReport}>
      <FileText size={25} strokeWidth={1.5} />
      <strong>暂时没有可展示的报告</strong>
      <span>完成一次周报任务后，报告内容会显示在这里。</span>
    </div>;
  }
  const blocks = markdown.split(/\n{2,}/).map(x => x.trim()).filter(Boolean);
  return <div className={styles.reportBody}>
    {blocks.map((block, index) => {
      const lines = block.split("\n").map(x => x.trim()).filter(Boolean);
      if (!lines.length) return null;
      const first = lines[0];
      if (first.startsWith("# ")) return <h2 key={index}>{first.slice(2)}</h2>;
      if (first.startsWith("## ")) return <h3 key={index}>{first.slice(3)}</h3>;
      if (first.startsWith("### ")) return <h4 key={index}>{first.slice(4)}</h4>;
      if (lines.every(line => /^[-*]\s/.test(line))) {
        return <ul key={index}>{lines.map((line, i) => <li key={i}>{line.replace(/^[-*]\s/, "")}</li>)}</ul>;
      }
      if (lines.every(line => /^\d+[.)]\s/.test(line))) {
        return <ol key={index}>{lines.map((line, i) => <li key={i}>{line.replace(/^\d+[.)]\s/, "")}</li>)}</ol>;
      }
      return <p key={index}>{lines.join(" ")}</p>;
    })}
  </div>;
}

function EmptyState({ icon: Icon, title, description, action }: {
  icon: typeof FileText; title: string; description: string; action?: React.ReactNode;
}) {
  return <div className={styles.emptyState}>
    <div className={styles.emptyIcon}><Icon size={23} strokeWidth={1.5} /></div>
    <h3>{title}</h3>
    <p>{description}</p>
    {action}
  </div>;
}

export default function ResearchAtlasV1() {
  const [auth, setAuth] = useState<boolean | null>(null);
  const [teamMode, setTeamMode] = useState(false);
  const [member, setMember] = useState<TeamMember | null>(null);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginBusy, setLoginBusy] = useState(false);

  const [section, setSection] = useState<Section>("chat");
  const [settingsTab, setSettingsTab] = useState<SettingsTab>("profile");
  const [chatScope, setChatScope] = useState<ChatScope>("private");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const [tasks, setTasks] = useState<Task[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profileDraft, setProfileDraft] = useState<Profile>(emptyProfile);
  const [profileVersion, setProfileVersion] = useState(0);
  const [brief, setBrief] = useState("");
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [question, setQuestion] = useState("");
  const [taskQuery, setTaskQuery] = useState("");
  const [taskFilter, setTaskFilter] = useState<"all" | "explore" | "weekly">("all");
  const [showTrace, setShowTrace] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [members, setMembers] = useState<TeamMember[]>([]);
  const [audits, setAudits] = useState<TeamAudit[]>([]);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteName, setInviteName] = useState("");
  const [invitePassword, setInvitePassword] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "researcher" | "viewer">("researcher");

  const canAdmin = !teamMode || member?.role === "admin";
  const canEdit = !teamMode || member?.role === "admin" || member?.role === "researcher";

  const load = useCallback(async () => {
    setLoading(true);
    const results = await Promise.allSettled([
      api<{ items: Task[] }>("tasks"),
      api<{ profile: Profile | null; version?: number }>("profile"),
      api<{ markdown: string; profile_ready?: boolean }>("brief"),
    ]);
    const [taskResult, profileResult, briefResult] = results;
    if (taskResult.status === "fulfilled") setTasks(taskResult.value.items);
    if (profileResult.status === "fulfilled") {
      const nextProfile = profileResult.value.profile;
      setProfile(nextProfile);
      setProfileDraft(nextProfile ? {
        ...emptyProfile,
        ...nextProfile,
        team: { ...emptyProfile.team, ...(nextProfile.team || {}) },
        research_lines: nextProfile.research_lines || [],
      } : emptyProfile);
      setProfileVersion(profileResult.value.version || 0);
    }
    if (briefResult.status === "fulfilled") {
      setBrief(briefResult.value.markdown || "");
    }
    const failed = results.find(x => x.status === "rejected");
    if (failed?.status === "rejected") {
      setError(failed.reason instanceof Error ? failed.reason.message : "部分数据加载失败");
    } else {
      setError("");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetch("/api/session", { cache: "no-store" })
      .then(response => response.json())
      .then(data => {
        setTeamMode(Boolean(data.team));
        setMember(data.member || null);
        setAuth(Boolean(data.authenticated));
      })
      .catch(() => setAuth(false));
  }, []);

  useEffect(() => {
    if (auth) void load();
  }, [auth, load]);

  useEffect(() => {
    if (!auth || !teamMode || member?.role !== "admin") return;
    void Promise.allSettled([
      api<{ items: TeamMember[] }>("team/members"),
      api<{ items: TeamAudit[] }>("team/audit"),
    ]).then(([memberResult, auditResult]) => {
      if (memberResult.status === "fulfilled") setMembers(memberResult.value.items);
      if (auditResult.status === "fulfilled") setAudits(auditResult.value.items);
    });
  }, [auth, teamMode, member?.role]);

  useEffect(() => {
    if (!auth || !tasks.some(task => task.status === "queued" || task.status === "running")) return;
    const timer = window.setInterval(async () => {
      try {
        const response = await api<{ items: Task[] }>("tasks");
        setTasks(response.items);
        if (!response.items.some(task => task.status === "queued" || task.status === "running")) {
          void load();
        }
      } catch {
        // Preserve the last known task state; the next poll can recover.
      }
    }, 4000);
    return () => window.clearInterval(timer);
  }, [auth, tasks, load]);

  const exploreTasks = useMemo(
    () => tasks.filter(task => task.kind === "explore"),
    [tasks],
  );
  const weeklyTasks = useMemo(
    () => tasks.filter(task => task.kind === "weekly"),
    [tasks],
  );
  const selectedTask = tasks.find(task => task.id === selectedTaskId) || null;
  const selectedExploreTask = selectedTask?.kind === "explore" ? selectedTask : null;
  const latestWeeklyTask = weeklyTasks[0] || null;
  const visibleTasks = tasks.filter(task => {
    const matchesType = taskFilter === "all"
      || (taskFilter === "explore" && task.kind === "explore")
      || (taskFilter === "weekly" && task.kind === "weekly");
    const haystack = (task.query || "") + " " + (task.result?.answer || "");
    return matchesType && haystack.toLowerCase().includes(taskQuery.toLowerCase());
  });

  function changeSection(next: Section) {
    setSection(next);
    setMobileNavOpen(false);
    setNotice("");
    setError("");
  }

  async function login() {
    setLoginBusy(true);
    setError("");
    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: loginPassword, email: loginEmail }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "登录失败");
      setAuth(true);
      setLoginPassword("");
      if (data.member) setMember(data.member);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "登录失败");
    } finally {
      setLoginBusy(false);
    }
  }

  async function logout() {
    await fetch("/api/logout", { method: "POST" });
    setAuth(false);
    setMember(null);
    setTasks([]);
    setProfile(null);
    setMembers([]);
  }

  async function submitTask(kind: Task["kind"], query = "") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const task = await api<Task>("tasks", {
        method: "POST",
        body: JSON.stringify({ kind, query }),
      });
      setTasks(current => [task, ...current.filter(item => item.id !== task.id)]);
      setSelectedTaskId(task.id);
      setQuestion("");
      if (kind === "explore") changeSection("chat");
      setNotice(kind === "weekly"
        ? "团队周报任务已提交。完成后会自动更新报告。"
        : "定向科研任务已提交。可在任务记录中查看进度和结果。");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "任务提交失败");
    } finally {
      setBusy(false);
    }
  }

  async function dispatchTask(task: Task) {
    if (task.status !== "queued") return;
    setBusy(true);
    setError("");
    try {
      await api<Task>("tasks/" + task.id + "/dispatch", { method: "POST" });
      setNotice("已请求后台执行排队任务。");
      void load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "请求执行失败");
    } finally {
      setBusy(false);
    }
  }

  function downloadReport(markdown: string, filename: string) {
    if (!markdown.trim()) return;
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  function updateTeamField(field: "name" | "mission" | "priorities", value: string) {
    setProfileDraft(current => ({
      ...current,
      team: {
        ...(current.team || {}),
        [field]: field === "priorities" ? value.split("\n").map(x => x.trim()).filter(Boolean) : value,
      },
    }));
  }

  function updateResearchLine(index: number, patch: Partial<ResearchLine>) {
    setProfileDraft(current => ({
      ...current,
      research_lines: (current.research_lines || []).map((line, lineIndex) =>
        lineIndex === index ? { ...line, ...patch } : line),
    }));
  }

  function addResearchLine() {
    const line: ResearchLine = {
      id: "line_" + Date.now().toString(36),
      name: "",
      problem: "",
      keywords: [],
      search_queries: [],
      method_queries: [],
    };
    setProfileDraft(current => ({
      ...current,
      research_lines: [...(current.research_lines || []), line],
    }));
  }

  function removeResearchLine(index: number) {
    setProfileDraft(current => ({
      ...current,
      research_lines: (current.research_lines || []).filter((_, lineIndex) => lineIndex !== index),
    }));
  }

  async function saveProfile() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const payload = {
        ...profileDraft,
        expected_version: teamMode ? profileVersion : undefined,
      };
      const result = await api<{ profile: Profile; version: number }>("profile", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setProfile(result.profile);
      setProfileVersion(result.version || 0);
      setProfileDraft({
        ...emptyProfile,
        ...result.profile,
        team: { ...emptyProfile.team, ...(result.profile.team || {}) },
        research_lines: result.profile.research_lines || [],
      });
      setNotice("团队研究画像已保存。后续团队科研任务将使用新版本画像。");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "画像保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function inviteMember() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const created = await api<TeamMember>("team/members", {
        method: "POST",
        body: JSON.stringify({
          email: inviteEmail,
          name: inviteName,
          temporary_password: invitePassword,
          role: inviteRole,
        }),
      });
      setMembers(current => [...current, created]);
      setInviteEmail("");
      setInviteName("");
      setInvitePassword("");
      setNotice("成员已创建。请通过安全渠道单独告知临时密码。");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "创建成员失败");
    } finally {
      setBusy(false);
    }
  }

  async function toggleMember(memberRecord: TeamMember) {
    setBusy(true);
    setError("");
    try {
      const updated = await api<TeamMember>("team/members/" + memberRecord.id, {
        method: "PATCH",
        body: JSON.stringify({ active: !memberRecord.active }),
      });
      setMembers(current => current.map(item => item.id === updated.id ? updated : item));
      setNotice("成员状态已更新，操作已写入审计记录。");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "成员状态更新失败");
    } finally {
      setBusy(false);
    }
  }

  if (auth === null) {
    return <div className={styles.loadingScreen}><Loader2 className={styles.spin} size={22} />正在连接研究空间…</div>;
  }

  if (!auth) {
    return <div className={styles.loginPage}>
      <div className={styles.loginPanel}>
        <div className={styles.brandMark}>RA</div>
        <div className={styles.eyebrow}>RESEARCH ATLAS</div>
        <h1>登录研究空间</h1>
        <p>进入团队与个人科研工作区。</p>
        <form onSubmit={event => { event.preventDefault(); void login(); }} className={styles.loginForm}>
          {teamMode && <label>团队成员邮箱
            <input type="email" value={loginEmail} onChange={event => setLoginEmail(event.target.value)} autoComplete="username" required />
          </label>}
          <label>访问密码
            <input type="password" value={loginPassword} onChange={event => setLoginPassword(event.target.value)} autoComplete="current-password" required />
          </label>
          {error && <div className={styles.inlineError}><AlertCircle size={15} />{error}</div>}
          <button className={styles.primaryButton} type="submit" disabled={loginBusy}>
            {loginBusy ? <Loader2 className={styles.spin} size={16} /> : null}登录
          </button>
        </form>
        <div className={styles.loginFoot}>科研资料按账户权限访问。请勿在公共设备保存登录状态。</div>
      </div>
    </div>;
  }

  const pageName = sectionNames[section];
  const recentExploreTasks = exploreTasks.slice(0, 8);

  return <div className={styles.appShell}>
    {mobileNavOpen && <button className={styles.scrim} onClick={() => setMobileNavOpen(false)} aria-label="关闭导航" />}
    <aside className={styles.iconRail}>
      <div className={styles.railBrand}>RA</div>
      <button className={styles.railButton + (section === "chat" ? " " + styles.railActive : "")}
        onClick={() => changeSection("chat")} title="对话" aria-label="对话">
        <MessageCircle size={20} />
      </button>
      <button className={styles.railButton + (section !== "chat" ? " " + styles.railActive : "")}
        onClick={() => changeSection("team-weekly")} title="研究台" aria-label="研究台">
        <BookOpen size={20} />
      </button>
      <div className={styles.railSpacer} />
      <button className={styles.railButton} onClick={() => void logout()} title="退出登录" aria-label="退出登录">
        <LogOut size={18} />
      </button>
      <div className={styles.railAvatar}>{(member?.name || "R").slice(0, 1).toUpperCase()}</div>
    </aside>

    <aside className={styles.sidePanel + (mobileNavOpen ? " " + styles.sidePanelOpen : "")}>
      <div className={styles.sideHeader}>
        <div>
          <div className={styles.eyebrow}>RESEARCH ATLAS</div>
          <h2>{section === "chat" ? "对话" : "研究台"}</h2>
        </div>
        <button className={styles.mobileClose} onClick={() => setMobileNavOpen(false)} aria-label="关闭侧栏"><X size={18} /></button>
      </div>

      {section === "chat" ? <div className={styles.sideContent}>
        <div className={styles.sideSectionLabel}>对话空间</div>
        <div className={styles.scopeSwitch}>
          <button className={chatScope === "private" ? styles.scopeActive : ""} onClick={() => setChatScope("private")}>
            <UserRound size={15} />私人对话
          </button>
          <button className={chatScope === "team" ? styles.scopeActive : ""} onClick={() => setChatScope("team")}>
            <Users size={15} />团队对话
          </button>
        </div>
        <div className={styles.sideSectionLabel + " " + styles.sideSectionWithAction}>
          最近研究任务
          <span>{recentExploreTasks.length}</span>
        </div>
        {recentExploreTasks.length ? recentExploreTasks.map(task => (
          <button key={task.id} className={styles.taskNavItem + (selectedTaskId === task.id ? " " + styles.taskNavActive : "")}
            onClick={() => { setSelectedTaskId(task.id); setChatScope("private"); setMobileNavOpen(false); }}>
            <FileText size={15} />
            <span>{task.query || "未命名研究任务"}<small>{shortDate(task.created_at)} · {statusText(task.status)}</small></span>
          </button>
        )) : <div className={styles.sideEmpty}>完成的科研探索会显示在这里。</div>}
        <div className={styles.sideHint}>普通对话与深度研究共用同一入口。当前后端的研究调用以单次任务方式执行。</div>
      </div> : <nav className={styles.sideContent} aria-label="研究台导航">
        <div className={styles.sideSectionLabel}>研究工作</div>
        <button className={styles.navItem + (section === "team-weekly" ? " " + styles.navActive : "")}
          onClick={() => changeSection("team-weekly")}><Users size={17} /><span>团队周报</span></button>
        <button className={styles.navItem + (section === "personal-weekly" ? " " + styles.navActive : "")}
          onClick={() => changeSection("personal-weekly")}><UserRound size={17} /><span>个人周报</span></button>
        <button className={styles.navItem + (section === "tasks" ? " " + styles.navActive : "")}
          onClick={() => changeSection("tasks")}><Search size={17} /><span>定向科研任务</span></button>
        <div className={styles.sideSectionLabel}>设置</div>
        <button className={styles.navItem + (section === "settings" ? " " + styles.navActive : "")}
          onClick={() => changeSection("settings")}><Settings2 size={17} /><span>研究设置</span></button>
      </nav>}

      <div className={styles.sideFooter}>
        <span>{teamMode ? "团队工作空间" : "个人访问模式"}</span>
        <span>{member?.role === "admin" ? "管理员" : member?.role === "researcher" ? "研究成员" : member?.role === "viewer" ? "只读成员" : "已登录"}</span>
      </div>
    </aside>

    <main className={styles.mainArea}>
      <header className={styles.topBar}>
        <div className={styles.topLeft}>
          <button className={styles.mobileMenu} onClick={() => setMobileNavOpen(true)} aria-label="打开导航"><Menu size={19} /></button>
          <div className={styles.breadcrumb}><span>{section === "chat" ? "对话" : "研究台"}</span><ChevronRight size={13} /><strong>{pageName}</strong></div>
        </div>
        <div className={styles.topRight}>
          <span className={styles.accountName}>{member?.name || "研究空间"}</span>
          <button className={styles.iconAction} onClick={() => void load()} disabled={loading} title="刷新数据" aria-label="刷新数据">
            {loading ? <Loader2 size={16} className={styles.spin} /> : <RefreshCw size={16} />}
          </button>
        </div>
      </header>

      <div className={styles.contentArea}>
        {error && <div className={styles.alertError}><AlertCircle size={16} /><span>{error}</span><button onClick={() => setError("")} aria-label="关闭"><X size={15} /></button></div>}
        {notice && <div className={styles.alertSuccess}><CheckCircle2 size={16} /><span>{notice}</span><button onClick={() => setNotice("")} aria-label="关闭"><X size={15} /></button></div>}

        {section === "chat" && <section className={styles.chatPage}>
          <PageHeader eyebrow="RESEARCH CONVERSATION" title="对话" description="围绕研究问题交流，按需调用科研分析与深度研究。" />
          {chatScope === "private" ? <>
            <div className={styles.capabilityNotice}>
              <ShieldCheck size={16} />
              <span>当前已连接真实 Research Agent，但后端仍以单次研究任务保存结果；独立私人多轮会话和私有数据隔离尚未完成。请勿将需要严格保密的内容视为私人存储。</span>
            </div>
            <div className={styles.chatWorkspace}>
              <div className={styles.chatMain}>
                {selectedExploreTask ? <div className={styles.chatResult}>
                  <div className={styles.messageUser}>
                    <div className={styles.messageAvatar}>我</div>
                    <div><span>研究问题</span><p>{selectedExploreTask.query}</p></div>
                  </div>
                  <div className={styles.messageAssistant}>
                    <div className={styles.assistantMark}>RA</div>
                    <div className={styles.assistantContent}>
                      <div className={styles.assistantTitle}>Research Agent <Status status={selectedExploreTask.status} /></div>
                      {selectedExploreTask.status === "completed" && <ReportBody markdown={selectedExploreTask.result?.answer || "任务已完成，但没有返回文本结果。"} />}
                      {selectedExploreTask.status === "failed" && <div className={styles.inlineError}><AlertCircle size={15} />{selectedExploreTask.error || "任务执行失败"}</div>}
                      {(selectedExploreTask.status === "queued" || selectedExploreTask.status === "running") && <div className={styles.runningState}><Loader2 size={17} className={styles.spin} />研究任务正在执行，结果会自动更新。</div>}
                      {!!selectedExploreTask.result?.sources?.length && <div className={styles.sourceList}>
                        <div className={styles.sourceHeading}>本次引用来源 · {selectedExploreTask.result.sources.length}</div>
                        {selectedExploreTask.result.sources.map(paper => <a key={paper.id} href={paper.url || undefined} target="_blank" rel="noopener noreferrer">
                          <BookOpen size={14} /><span>{paper.title}<small>{paper.venue || "来源待核验"} · {paper.published || "日期未知"}</small></span><ArrowUpRight size={13} />
                        </a>)}
                      </div>}
                      <button className={styles.traceToggle} onClick={() => setShowTrace(value => !value)}>
                        <ChevronDown size={14} />{showTrace ? "收起执行记录" : "查看执行记录"}
                      </button>
                      {showTrace && <div className={styles.traceList}>
                        {selectedExploreTask.events.map((event, index) => <div key={index}><span>{dateTime(event.at)}</span><strong>{event.step}</strong><p>{event.detail}</p></div>)}
                        {selectedExploreTask.error && <div className={styles.traceError}>{selectedExploreTask.error}</div>}
                      </div>}
                      {selectedExploreTask.status === "queued" && canEdit && <button className={styles.secondaryButton} onClick={() => void dispatchTask(selectedExploreTask)} disabled={busy}>请求后台执行</button>}
                    </div>
                  </div>
                </div> : <EmptyState icon={MessageCircle} title="开始一项科研探索" description="描述研究问题、已有基础和希望解决的瓶颈。系统将创建一项真实研究任务，并返回文献证据与分析结果。" />}
                <form className={styles.composer} onSubmit={event => { event.preventDefault(); void submitTask("explore", question); }}>
                  <textarea value={question} onChange={event => setQuestion(event.target.value)} maxLength={2000}
                    rows={3} placeholder="例如：基于我现有的研究，哪些跨学科方法可能解决当前的泛化瓶颈？" disabled={!canEdit || busy} />
                  <div className={styles.composerBottom}>
                    <span>{question.length}/2000 · 每次提交创建一项独立科研任务</span>
                    <button className={styles.primaryButton} type="submit" disabled={!canEdit || busy || question.trim().length < 6}>
                      {busy ? <Loader2 size={15} className={styles.spin} /> : <Send size={15} />}开始研究
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </> : <div className={styles.teamChatPending}>
            <div className={styles.pendingIcon}><Users size={24} /></div>
            <div className={styles.eyebrow}>TEAM CONVERSATION</div>
            <h2>团队共同对话界面已预留</h2>
            <p>当前后端尚未提供团队多轮会话、成员发言记录和 @GPT 触发机制。为避免将普通研究任务误显示为共享聊天，这里暂不开放发送入口。</p>
            <div className={styles.pendingRule}>后续按既定规则实现：普通成员消息不触发模型，只有 @GPT 或主动调用 AI 时才启动科研能力。</div>
          </div>}
        </section>}

        {section === "team-weekly" && <section>
          <PageHeader eyebrow="SC01 · TEAM RESEARCH BRIEF" title="团队周报" description="持续扫描团队关注的研究来源，整理值得团队跟进的论文、方法和研究问题。"
            action={<button className={styles.primaryButton} onClick={() => void submitTask("weekly")} disabled={!canEdit || busy || !profile}>
              {busy ? <Loader2 size={15} className={styles.spin} /> : <RefreshCw size={15} />}生成本期周报
            </button>} />
          <div className={styles.reportMetaRow}>
            <div><span>团队研究画像</span><strong>{profile?.team?.name || "尚未建立"}</strong></div>
            <div><span>最近一次生成</span><strong>{shortDate(latestWeeklyTask?.updated_at || latestWeeklyTask?.created_at)}</strong></div>
            <div><span>历史报告</span><strong>{weeklyTasks.length} 期</strong></div>
            {latestWeeklyTask && <div><span>最近任务状态</span><Status status={latestWeeklyTask.status} /></div>}
          </div>
          {!profile && <div className={styles.capabilityNotice}><AlertCircle size={16} /><span>请先在研究设置中建立团队研究画像，才能生成团队周报。</span></div>}
          <div className={styles.reportLayout}>
            <article className={styles.reportPanel}>
              <div className={styles.panelHeading}>
                <div><div className={styles.eyebrow}>LATEST REPORT</div><h2>最新一期</h2></div>
                <button className={styles.iconAction} onClick={() => downloadReport(latestWeeklyTask?.result?.answer || brief, "research-atlas-team-weekly.md")}
                  disabled={!(latestWeeklyTask?.result?.answer || brief)} title="下载 Markdown"><Download size={16} /></button>
              </div>
              <ReportBody markdown={latestWeeklyTask?.result?.answer || brief} />
              {latestWeeklyTask?.status === "running" && <div className={styles.runningState}><Loader2 size={16} className={styles.spin} />周报生成中，完成后会更新报告内容。</div>}
            </article>
            <aside className={styles.historyPanel}>
              <div className={styles.panelHeading}><div><div className={styles.eyebrow}>ARCHIVE</div><h2>历史周报</h2></div><span>{weeklyTasks.length}</span></div>
              {weeklyTasks.length ? weeklyTasks.map(task => <button key={task.id} className={styles.historyItem}
                onClick={() => setSelectedTaskId(task.id)}>
                <span className={styles.historyIcon}><FileText size={15} /></span>
                <span><strong>{shortDate(task.created_at)} · 团队周报</strong><small>{statusText(task.status)} · {task.id.slice(0, 8)}</small></span>
                <ChevronRight size={15} />
              </button>) : <div className={styles.sideEmpty}>完成首次生成后，历史周报会保存在这里。</div>}
              {selectedTask?.kind === "weekly" && <div className={styles.selectedHistory}>
                <strong>已选择：{dateTime(selectedTask.created_at)}</strong>
                <p>{selectedTask.result?.answer ? "该期报告已保存，可下载最新报告。" : selectedTask.error || "该期任务尚无报告内容。"}</p>
                <button className={styles.textButton} onClick={() => downloadReport(selectedTask.result?.answer || "", "team-weekly-" + selectedTask.id.slice(0, 8) + ".md")} disabled={!selectedTask.result?.answer}>下载该期报告</button>
              </div>}
            </aside>
          </div>
        </section>}

        {section === "personal-weekly" && <section>
          <PageHeader eyebrow="SC02 · PERSONAL RESEARCH BRIEF" title="个人周报" description="根据个人研究画像和关注范围，持续发现与你当前研究相关的新论文、方法与研究机会。" />
          <div className={styles.personalIntro}>
            <div className={styles.personalIcon}><UserRound size={22} /></div>
            <div><div className={styles.eyebrow}>PERSONAL RESEARCH</div><h2>个人研究动态</h2>
              <p>个人画像、独立周报存储与定时生成接口尚未接入当前生产后端。为避免将团队周报误作个人结果，本页面暂不展示模拟报告。</p>
            </div>
          </div>
          <div className={styles.personalGrid}>
            <div className={styles.personalCard}>
              <span>个人研究画像</span><strong>待接入</strong><p>用于识别个人研究兴趣、方法基础和当前问题。</p>
            </div>
            <div className={styles.personalCard}>
              <span>个性化文献发现</span><strong>待接入</strong><p>基于个人关注方向检索论文和跨领域方法。</p>
            </div>
            <div className={styles.personalCard}>
              <span>个人报告归档</span><strong>待接入</strong><p>个人周报独立保存，不自动进入团队共享空间。</p>
            </div>
          </div>
          <div className={styles.pendingFootnote}><ShieldCheck size={16} />个人周报需要独立的个人画像、访问控制和报告存储；这些接口完成后再开放生成操作。</div>
        </section>}

        {section === "tasks" && <section>
          <PageHeader eyebrow="SC03 · DIRECTED RESEARCH" title="定向科研任务" description="针对具体研究问题开展文献检索、方法迁移和证据审查，并保存完整研究报告。"
            action={<button className={styles.primaryButton} onClick={() => { setSection("chat"); setChatScope("private"); }}><Plus size={15} />新建任务</button>} />
          <div className={styles.taskToolbar}>
            <div className={styles.taskFilters}>
              <button className={taskFilter === "all" ? styles.filterActive : ""} onClick={() => setTaskFilter("all")}>全部</button>
              <button className={taskFilter === "explore" ? styles.filterActive : ""} onClick={() => setTaskFilter("explore")}>定向研究</button>
              <button className={taskFilter === "weekly" ? styles.filterActive : ""} onClick={() => setTaskFilter("weekly")}>周报任务</button>
            </div>
            <label className={styles.searchInput}><Search size={15} /><input value={taskQuery} onChange={event => setTaskQuery(event.target.value)} placeholder="搜索任务问题或结果" /></label>
          </div>
          <div className={styles.taskPageGrid}>
            <div className={styles.taskList}>
              {visibleTasks.length ? visibleTasks.map(task => <button key={task.id}
                className={styles.taskListItem + (selectedTaskId === task.id ? " " + styles.taskListSelected : "")}
                onClick={() => setSelectedTaskId(task.id)}>
                <div className={styles.taskListTop}><span>{task.kind === "weekly" ? "团队周报" : task.kind === "sync" ? "文献更新" : "定向研究"}</span><Status status={task.status} /></div>
                <strong>{task.query || (task.kind === "weekly" ? "团队科研周报" : "未命名任务")}</strong>
                <small>{dateTime(task.created_at)}</small>
              </button>) : <EmptyState icon={Search} title="没有匹配的任务" description="调整筛选条件，或从对话创建一项新的定向研究任务。" />}
            </div>
            <div className={styles.taskDetail}>
              {selectedTask ? <>
                <div className={styles.panelHeading}>
                  <div><div className={styles.eyebrow}>TASK DETAIL · {selectedTask.id.slice(0, 8)}</div>
                    <h2>{selectedTask.query || (selectedTask.kind === "weekly" ? "团队科研周报" : "任务详情")}</h2></div>
                  <Status status={selectedTask.status} />
                </div>
                <div className={styles.taskDetailMeta}><span>创建于 {dateTime(selectedTask.created_at)}</span><span>更新于 {dateTime(selectedTask.updated_at)}</span></div>
                {selectedTask.error && <div className={styles.inlineError}><AlertCircle size={15} />{selectedTask.error}</div>}
                {selectedTask.result?.answer && <ReportBody markdown={selectedTask.result.answer} />}
                {selectedTask.result?.sources?.length ? <div className={styles.sourceList}>
                  <div className={styles.sourceHeading}>引用来源</div>
                  {selectedTask.result.sources.map(paper => <a key={paper.id} href={paper.url || undefined} target="_blank" rel="noopener noreferrer">
                    <BookOpen size={14} /><span>{paper.title}<small>{paper.venue || "来源待核验"} · {paper.published || "日期未知"}</small></span><ArrowUpRight size={13} />
                  </a>)}
                </div> : null}
                <div className={styles.traceList}>
                  <div className={styles.sourceHeading}>执行记录</div>
                  {selectedTask.events.map((event, index) => <div key={index}><span>{dateTime(event.at)}</span><strong>{event.step}</strong><p>{event.detail}</p></div>)}
                </div>
                {selectedTask.status === "queued" && canEdit && <button className={styles.secondaryButton} onClick={() => void dispatchTask(selectedTask)} disabled={busy}>请求后台执行</button>}
                {selectedTask.status === "completed" && selectedTask.result?.answer && <button className={styles.secondaryButton} onClick={() => downloadReport(selectedTask.result.answer || "", "research-task-" + selectedTask.id.slice(0, 8) + ".md")}><Download size={14} />下载报告</button>}
              </> : <EmptyState icon={FileText} title="选择一项研究任务" description="任务详情、执行状态、文献引用和最终报告会显示在这里。" />}
            </div>
          </div>
        </section>}

        {section === "settings" && <section>
          <PageHeader eyebrow="RESEARCH SETTINGS" title="研究设置" description="管理支撑团队周报、个人研究和定向科研任务的必要信息。" />
          <div className={styles.settingsLayout}>
            <nav className={styles.settingsTabs}>
              <button className={settingsTab === "profile" ? styles.settingsTabActive : ""} onClick={() => setSettingsTab("profile")}><UserRound size={16} />研究画像</button>
              <button className={settingsTab === "sources" ? styles.settingsTabActive : ""} onClick={() => setSettingsTab("sources")}><BookOpen size={16} />文献来源</button>
              <button className={settingsTab === "interests" ? styles.settingsTabActive : ""} onClick={() => setSettingsTab("interests")}><Search size={16} />关注主题</button>
              {teamMode && <button className={settingsTab === "members" ? styles.settingsTabActive : ""} onClick={() => setSettingsTab("members")}><Users size={16} />成员权限</button>}
            </nav>

            {settingsTab === "profile" && <div className={styles.settingsContent}>
              <section className={styles.settingsCard}>
                <div className={styles.panelHeading}>
                  <div><div className={styles.eyebrow}>TEAM PROFILE</div><h2>团队研究画像</h2></div>
                  <span className={styles.versionLabel}>版本 V{profileVersion}</span>
                </div>
                <p className={styles.settingsDescription}>团队画像用于团队周报和共享科研任务。仅管理员可以修改正式画像。</p>
                <div className={styles.formGrid}>
                  <label>团队名称<input value={profileDraft.team?.name || ""} onChange={event => updateTeamField("name", event.target.value)} disabled={!canAdmin} placeholder="例如：城市科学与规划研究团队" /></label>
                  <label>研究目标<input value={profileDraft.goals || ""} onChange={event => setProfileDraft(current => ({ ...current, goals: event.target.value }))} disabled={!canAdmin} placeholder="团队希望长期解决的科研问题" /></label>
                </div>
                <label className={styles.fullField}>团队定位<textarea rows={3} value={profileDraft.team?.mission || ""} onChange={event => updateTeamField("mission", event.target.value)} disabled={!canAdmin} placeholder="描述团队研究范围、学科交叉特点和主要贡献方向。" /></label>
                <label className={styles.fullField}>重点关注<textarea rows={2} value={(profileDraft.team?.priorities || []).join("\n")} onChange={event => updateTeamField("priorities", event.target.value)} disabled={!canAdmin} placeholder="每行填写一个重点方向" /></label>
                <div className={styles.sectionSubhead}><h3>研究主线</h3><span>{profileDraft.research_lines?.length || 0} 条</span></div>
                {(profileDraft.research_lines || []).map((line, index) => <div className={styles.lineEditor} key={line.id}>
                  <div className={styles.lineEditorTop}><strong>研究主线 {index + 1}</strong>{canAdmin && <button onClick={() => removeResearchLine(index)} type="button" aria-label="删除研究主线"><X size={15} /></button>}</div>
                  <label>名称<input value={line.name} onChange={event => updateResearchLine(index, { name: event.target.value })} disabled={!canAdmin} /></label>
                  <label>核心问题<textarea rows={2} value={line.problem} onChange={event => updateResearchLine(index, { problem: event.target.value })} disabled={!canAdmin} /></label>
                  <div className={styles.formGrid}>
                    <label>问题检索词<textarea rows={2} value={(line.search_queries || []).join("\n")} onChange={event => updateResearchLine(index, { search_queries: event.target.value.split("\n").map(x => x.trim()).filter(Boolean) })} disabled={!canAdmin} placeholder="每行一条检索表达式" /></label>
                    <label>方法检索词<textarea rows={2} value={(line.method_queries || []).join("\n")} onChange={event => updateResearchLine(index, { method_queries: event.target.value.split("\n").map(x => x.trim()).filter(Boolean) })} disabled={!canAdmin} placeholder="每行一条方法表达式" /></label>
                  </div>
                </div>)}
                {canAdmin && <div className={styles.profileActions}>
                  <button className={styles.secondaryButton} type="button" onClick={addResearchLine}><Plus size={14} />添加研究主线</button>
                  <button className={styles.primaryButton} type="button" onClick={() => void saveProfile()} disabled={busy}><Check size={15} />保存团队画像</button>
                </div>}
              </section>

              <section className={styles.settingsCard}>
                <div className={styles.panelHeading}><div><div className={styles.eyebrow}>PERSONAL PROFILE</div><h2>个人研究画像</h2></div><span className={styles.pendingLabel}>待接入</span></div>
                <p className={styles.settingsDescription}>个人画像需要独立的成员级存储与权限接口。当前系统尚未提供该接口，因此不会将团队画像复制成个人画像。</p>
              </section>

              <section className={styles.settingsCard}>
                <div className={styles.panelHeading}><div><div className={styles.eyebrow}>REPORT SCHEDULE</div><h2>周报周期</h2></div><span className={styles.pendingLabel}>网页端暂未开放</span></div>
                <p className={styles.settingsDescription}>当前周报由服务端计划任务和 Worker 配置驱动。网页端尚未提供周期修改接口，因此此处只展示配置状态，不提供无效开关。</p>
              </section>
            </div>}

            {settingsTab === "sources" && <div className={styles.settingsContent}><AcademicSourceRegistry canAdmin={canAdmin} /></div>}
            {settingsTab === "interests" && <div className={styles.settingsContent}><InterestWatchlist canEdit={canEdit} /></div>}
            {settingsTab === "members" && <div className={styles.settingsContent}>
              {!teamMode ? <EmptyState icon={Users} title="团队账户尚未启用" description="成员管理仅在团队认证模式下开放。" /> :
                member?.role !== "admin" ? <EmptyState icon={ShieldCheck} title="仅管理员可管理成员" description="当前账户可以使用已授权的科研功能，但不能修改成员权限。" /> :
                <section className={styles.settingsCard}>
                  <div className={styles.panelHeading}><div><div className={styles.eyebrow}>TEAM ACCESS</div><h2>团队成员与权限</h2></div><span className={styles.versionLabel}>{members.length} 位成员</span></div>
                  <div className={styles.memberList}>
                    {members.map(person => <div className={styles.memberRow} key={person.id}>
                      <div className={styles.memberAvatar}>{person.name.slice(0, 1)}</div>
                      <div className={styles.memberInfo}><strong>{person.name}</strong><span>{person.email} · {person.role === "admin" ? "管理员" : person.role === "researcher" ? "研究成员" : "只读成员"}</span></div>
                      <span className={person.active ? styles.memberActive : styles.memberInactive}>{person.active ? "正常" : "已停用"}</span>
                      <button className={styles.textButton} disabled={busy || person.id === member.id} onClick={() => void toggleMember(person)}>{person.active ? "停用" : "启用"}</button>
                    </div>)}
                  </div>
                  <div className={styles.sectionSubhead}><h3>添加成员</h3></div>
                  <div className={styles.formGrid}>
                    <label>姓名<input value={inviteName} onChange={event => setInviteName(event.target.value)} placeholder="成员姓名" /></label>
                    <label>邮箱<input type="email" value={inviteEmail} onChange={event => setInviteEmail(event.target.value)} placeholder="name@university.edu" /></label>
                    <label>角色<select value={inviteRole} onChange={event => setInviteRole(event.target.value as typeof inviteRole)}><option value="researcher">研究成员</option><option value="viewer">只读成员</option><option value="admin">管理员</option></select></label>
                    <label>临时密码<input type="password" autoComplete="new-password" value={invitePassword} onChange={event => setInvitePassword(event.target.value)} placeholder="至少 12 位" /></label>
                  </div>
                  <div className={styles.profileActions}><button className={styles.primaryButton} disabled={busy || invitePassword.length < 12 || !inviteEmail || inviteName.length < 2} onClick={() => void inviteMember()}><Plus size={15} />创建成员</button></div>
                  <div className={styles.sectionSubhead}><h3>最近操作记录</h3></div>
                  {audits.length ? audits.slice(0, 12).map((audit, index) => <div className={styles.auditRow} key={audit.id || index}>
                    <strong>{audit.action}</strong><span>{audit.target} · {dateTime(audit.created_at)} · {audit.note}</span>
                  </div>) : <div className={styles.sideEmpty}>暂无审计记录。</div>}
                </section>}
            </div>}
          </div>
        </section>}
      </div>

      <footer className={styles.footer}><span>Research Atlas</span><span>科研发现与研究辅助工作区</span></footer>
    </main>
  </div>;
}
