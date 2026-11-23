"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle, ArrowUpRight, BookOpen, Check,
  CheckCircle2, ChevronDown, ChevronRight, Download, FileText,
  Loader2, LogOut, Menu, MessageCircle, Plus, RefreshCw, Search, Send,
  Settings2, ShieldCheck, SlidersHorizontal, UserRound, Users, X,
} from "lucide-react";
import { api } from "@/lib/api";
import type { PersonalResearchAsset, PersonalResearchProfile, Profile, ResearchLine, ResearchSourceLabel, Task, TaskSourceScope, TeamAudit, TeamMember } from "@/lib/types";
import AcademicSourceRegistry from "@/components/AcademicSourceRegistry";
import InterestWatchlist from "@/components/InterestWatchlist";
import TaskSourceScopeSettings, {TaskSourceRunPicker, SourceScopeInline, sourceScopeShort} from "@/components/TaskSourceScopes";
import type {SourceGroups} from "@/components/TaskSourceScopes";
import styles from "./ResearchAtlasV1.module.css";

type Section = "chat" | "team-weekly" | "personal-weekly" | "tasks" | "settings";
type SettingsTab = "profile" | "task-sources" | "sources" | "interests" | "members";
type ChatScope = "private" | "team";

const emptyProfile: Profile = {
  goals: "",
  team: { name: "", mission: "", priorities: [] },
  datasets: [],
  methods: [],
  excluded_terms: [],
  research_lines: [],
};

const initialPersonalProfile: PersonalResearchProfile = {
  goals: "围绕城市系统的测度、演化与运行机制，开展城市科学、空间数据科学与人工智能的交叉研究。重点关注城市交通与基础设施韧性、建成环境与儿童健康的跨区域关系、三维竖向城市化；强调从方法创新回到可解释的城市规律及规划意义。",
  methods: [
    "空间数据科学、GIS 与多源城市数据整合",
    "移动信令、OD 与时空行为分析",
    "城市网络科学、网络中心性与韧性分析",
    "机器学习、深度学习与跨区域泛化评估",
    "空间迁移、AOA/DI、样本增强与图邻域聚合",
    "三维城市形态、建筑高度与垂直功能测度",
    "AI 辅助科研发现、文献证据审查与可证伪研究设计"
  ],
  excluded_terms: [],
  research_lines: [
    {
      id: "metro_resilience",
      name: "地铁网络韧性与极端天气响应",
      problem: "研究极端天气扰动下地铁站点承压能力（To-resilience）与区间传导韧性（Through-resilience）如何耦合，客流重分配如何触发压力累积、容量阈值与级联失效，以及网络冗余和空间干预在什么条件下有效。以郑州“7·20”极端降雨地铁研究为代表性基础，继续寻找能够形成独立科学贡献的机制问题。",
      keywords: ["地铁网络韧性", "极端降雨", "To–Through resilience", "站点容量", "区间压力传播", "移动信令与 OD", "客流重分配", "级联失效", "网络冗余", "韧性规划干预"],
      search_queries: [
        "\"metro network resilience\" AND \"extreme rainfall\"",
        "\"To-resilience\" OR \"Through-resilience\" metro",
        "\"passenger flow redistribution\" metro disruption capacity",
        "\"cascading failure\" metro network resilience extreme weather",
        "\"network redundancy\" metro resilience intervention"
      ],
      method_queries: [
        "node-link coupled resilience metrics and network science",
        "mobile phone signalling OD and spatiotemporal mobility analysis",
        "capacity-constrained passenger flow redistribution simulation",
        "counterfactual network intervention and corridor redundancy",
        "multi-event validation of transport network resilience"
      ]
    },
    {
      id: "child_health_transfer",
      name: "儿童健康与建成环境的跨区域外推",
      problem: "研究建成环境与儿童健康结局关系在不同地区和城市之间的可迁移性，识别环境表征差异、标签稀疏与空间样本偏差如何共同导致外推失败；探索目标区域补样、人口与房价等 SES 信息、空间邻域聚合和多城市交叉验证，区分全局样本稀疏与空间覆盖偏差。",
      keywords: ["儿童健康", "建成环境", "跨城市迁移", "外部验证", "域偏移", "标签稀疏", "空间抽样偏差", "SES", "AOA", "DI", "图学习", "城市健康"],
      search_queries: [
        "\"built environment\" child health \"cross-city\" transferability",
        "\"spatial transfer learning\" health prediction built environment",
        "\"domain adaptation\" urban health sparse labels",
        "\"multi-city validation\" built environment child health",
        "\"spatially clustered labels\" external validation"
      ],
      method_queries: [
        "targeted sample augmentation and domain adaptation",
        "area of applicability AOA and dissimilarity index DI",
        "multi-city cross-validation with held-out city evaluation",
        "graph-based neighborhood aggregation and spatial representation learning",
        "SES reconstruction and teacher-student representation learning"
      ]
    },
    {
      id: "vertical_urbanization_3d",
      name: "三维竖向城市化与城市空间功能演化",
      problem: "从三维视角重新测度城市化，研究高层建筑增长、垂直空间功能化与经济周期之间的耦合演化；进一步探索智能化时代如何改变城市化的测量框架，以及 AI 如何重塑城市化路径、空间组织和发展机制。",
      keywords: ["三维城市化", "竖向城市化", "高层建筑增长", "垂直功能化", "建筑高度", "城市形态", "经济周期", "城市化测度", "AI 时代城市化", "城市演化"],
      search_queries: [
        "\"vertical urbanization\" high-rise buildings urbanization measurement",
        "\"3D urbanization\" vertical functional mix",
        "\"skyscraper growth\" economic cycles urban development",
        "\"vertical functionalization\" urban buildings floor-level",
        "\"AI\" \"urbanization measurement\" urban science"
      ],
      method_queries: [
        "three-dimensional building stock and vertical urban form measurement",
        "floor-level functional classification and vertical mixed use",
        "time-series analysis of skyscraper growth and economic cycles",
        "3D GIS and multi-source urban morphology representation",
        "comparative urbanization measurement in the AI age"
      ]
    }
  ],
  evidence: [
    {
      id: "shen_trd_2026",
      line_id: "metro_resilience",
      kind: "publication",
      title: "How metro networks respond to extreme rainfall: a coupled To–Through resilience perspective",
      url: "https://doi.org/10.1016/j.trd.2026.105654",
      note: "Transportation Research Part D, 162 (2027), Article 105654；在线发表 2026-10-06。"
    },
    {
      id: "shen_r645_gate_on",
      line_id: "metro_resilience",
      kind: "agent_report",
      title: "SC05 R6.4.5｜Science Gate On 原始报告（盲评 70/100）",
      url: "https://chatgpt.com/space/page_055ef567539c8191ac47eb1757794156",
      note: "DeepSeek 生成的原始报告；候选路线 R01–R03 均为 Hold，未获得科研新颖性或科学质量认证。"
    },
    {
      id: "shen_r645_gate_off",
      line_id: "metro_resilience",
      kind: "agent_report",
      title: "SC05 R6.4.5｜Science Gate Off 原始报告（盲评 38/100）",
      url: "https://chatgpt.com/space/page_a2f76795ccc881919e707e5d3e78d56a",
      note: "对照基线原始报告；保持历史冻结，不代表已验证研究方案。"
    },
    {
      id: "shen_r645_synthesis",
      line_id: "metro_resilience",
      kind: "agent_report",
      title: "Shen et al. 2026 TRD｜正式科研机会综合报告及 R6.4.5 盲评解盲",
      url: "https://chatgpt.com/space/page_f8fffbfcdd888191836e1c78077aa3e2",
      note: "ChatGPT 对两份原始报告和单评审盲评结果的综合解读；不是新增 DeepSeek 运行。"
    }
  ]
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
  const [chatMode, setChatMode] = useState<"gpt" | "research">("research");
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const [tasks, setTasks] = useState<Task[]>([]);
  const [sourceScopes, setSourceScopes] = useState<TaskSourceScope[]>([]);
  const [sourceCatalog, setSourceCatalog] = useState<ResearchSourceLabel[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profileDraft, setProfileDraft] = useState<Profile>(emptyProfile);
  const [profileVersion, setProfileVersion] = useState(0);
  const [personalProfileDraft, setPersonalProfileDraft] = useState<PersonalResearchProfile>(initialPersonalProfile);
  const [personalProfileVersion, setPersonalProfileVersion] = useState(0);
  const [personalProfileLoaded, setPersonalProfileLoaded] = useState(false);
  const [personalAssets, setPersonalAssets] = useState<PersonalResearchAsset[]>([]);
  const [personalAssetsLoaded, setPersonalAssetsLoaded] = useState(false);
  const [assetFormOpen, setAssetFormOpen] = useState(false);
  const [assetBusy, setAssetBusy] = useState(false);
  const [assetFilter, setAssetFilter] = useState<"all"|"publication"|"agent_report"|"experiment_result">("all");
  const [assetImportDoi, setAssetImportDoi] = useState("");
  const [assetImportTaskId, setAssetImportTaskId] = useState("");
  const [assetDraft, setAssetDraft] = useState({
    kind: "publication" as PersonalResearchAsset["kind"],
    title: "",
    summary: "",
    url: "",
    source_type: "manual",
    source_id: "",
    metadata: {} as Record<string, unknown>,
    line_ids: [] as string[],
  });
  const [brief, setBrief] = useState("");
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const [question, setQuestion] = useState("");
  const [taskSourceOverride, setTaskSourceOverride] = useState<SourceGroups|null>(null);
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
      api<{ items: TaskSourceScope[] }>("task-source-scopes"),
      api<{ items: ResearchSourceLabel[] }>("research-sources"),
      api<{ profile: PersonalResearchProfile | null; version: number }>("personal-profile"),
      api<{ items: PersonalResearchAsset[] }>("personal-assets"),
    ]);
    const [taskResult, profileResult, briefResult, scopeResult, catalogResult, personalProfileResult, personalAssetsResult] = results;
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
    if (scopeResult.status === "fulfilled") setSourceScopes(scopeResult.value.items);
    if (catalogResult.status === "fulfilled") setSourceCatalog(catalogResult.value.items);
    if (personalAssetsResult.status === "fulfilled") {
      setPersonalAssets(personalAssetsResult.value.items || []);
      setPersonalAssetsLoaded(true);
    } else {
      setPersonalAssets([]);
      setPersonalAssetsLoaded(false);
    }
    if (personalProfileResult.status === "fulfilled") {
      const saved = personalProfileResult.value.profile;
      const next = saved ? {
        ...initialPersonalProfile,
        ...saved,
        research_lines: saved.research_lines || [],
        methods: saved.methods || [],
        excluded_terms: saved.excluded_terms || [],
        evidence: saved.evidence || [],
      } : initialPersonalProfile;
      setPersonalProfileDraft(next);
      setPersonalProfileVersion(personalProfileResult.value.version || 0);
      setPersonalProfileLoaded(true);
    } else {
      setPersonalProfileLoaded(false);
    }
    // Older Render backends do not expose task-source-scopes yet; this must
    // not block existing chat and report workspaces.
    const failed = results.slice(0, 3).find(x => x.status === "rejected");
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
        setError(data.connection_error ? (data.detail || "团队认证服务暂不可用") : "");
        setAuth(Boolean(data.authenticated));
      })
      .catch(() => {
        setError("无法连接登录状态服务。请检查网络后重试；Render 免费实例首次唤醒可能需要约 40–60 秒。");
        setAuth(false);
      });
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
  const displayedWeeklyTask = selectedTask?.kind === "weekly" ? selectedTask : latestWeeklyTask;
  const displayedWeeklyReport = selectedTask?.kind === "weekly"
    ? (selectedTask.result?.answer || "")
    : latestWeeklyTask
      ? (latestWeeklyTask.result?.answer || "")
      : brief;
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
    setSourceScopes([]);
    setSourceCatalog([]);
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
        body: JSON.stringify({ kind, query, ...(kind === "explore" && taskSourceOverride ? {source_override:taskSourceOverride} : {}) }),
      });
      setTasks(current => [task, ...current.filter(item => item.id !== task.id)]);
      setSelectedTaskId(task.id);
      setQuestion("");
      if (kind === "explore") { setTaskSourceOverride(null); changeSection("chat"); }
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

  function updatePersonalResearchLine(index: number, patch: Partial<ResearchLine>) {
    setPersonalProfileDraft(current => ({
      ...current,
      research_lines: current.research_lines.map((line, lineIndex) =>
        lineIndex === index ? { ...line, ...patch } : line),
    }));
  }

  function addPersonalResearchLine() {
    const line: ResearchLine = {
      id: "personal_line_" + Date.now().toString(36),
      name: "",
      problem: "",
      keywords: [],
      search_queries: [],
      method_queries: [],
    };
    setPersonalProfileDraft(current => ({
      ...current,
      research_lines: [...current.research_lines, line],
    }));
  }

  function removePersonalResearchLine(index: number) {
    setPersonalProfileDraft(current => {
      const removedId = current.research_lines[index]?.id;
      return {
        ...current,
        research_lines: current.research_lines.filter((_, lineIndex) => lineIndex !== index),
        evidence: current.evidence.filter(item => item.line_id !== removedId),
      };
    });
  }

  async function savePersonalProfile() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api<{ profile: PersonalResearchProfile; version: number; updated_at?: string }>(
        "personal-profile",
        {
          method: "PUT",
          body: JSON.stringify({
            profile: personalProfileDraft,
            expected_version: personalProfileVersion,
          }),
        },
      );
      setPersonalProfileDraft({
        ...initialPersonalProfile,
        ...result.profile,
        research_lines: result.profile.research_lines || [],
        methods: result.profile.methods || [],
        excluded_terms: result.profile.excluded_terms || [],
        evidence: result.profile.evidence || [],
      });
      setPersonalProfileVersion(result.version);
      await refreshPersonalAssets();
      setNotice("个人研究画像和关联论文/报告已保存到当前账号，与团队画像独立存储。");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "个人画像保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function refreshPersonalAssets() {
    const result = await api<{ items: PersonalResearchAsset[] }>("personal-assets");
    setPersonalAssets(result.items || []);
    setPersonalAssetsLoaded(true);
  }

  async function savePersonalAsset() {
    if (!personalProfileVersion) {
      setError("请先保存个人研究画像，再录入关联资料。");
      return;
    }
    if (!assetDraft.title.trim()) {
      setError("请先填写资料标题。");
      return;
    }
    setAssetBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api<PersonalResearchAsset>("personal-assets", {
        method: "POST",
        body: JSON.stringify(assetDraft),
      });
      setPersonalAssets(current => [result, ...current.filter(item => item.id !== result.id)]);
      setAssetDraft({
        kind: "publication", title: "", summary: "", url: "",
        source_type: "manual", source_id: "", metadata: {}, line_ids: [],
      });
      setAssetFormOpen(false);
      setNotice("科研资料已保存到当前账号的个人资料库。");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "科研资料保存失败");
    } finally {
      setAssetBusy(false);
    }
  }

  async function importPersonalPaper() {
    if (!assetImportDoi.trim()) return;
    if (!personalProfileVersion) {
      setError("请先保存个人研究画像，再导入论文。");
      return;
    }
    setAssetBusy(true);
    setError("");
    try {
      const result = await api<PersonalResearchAsset>("personal-assets/import-paper", {
        method: "POST",
        body: JSON.stringify({
          doi: assetImportDoi.trim(),
          line_ids: assetDraft.line_ids,
        }),
      });
      setPersonalAssets(current => [result, ...current.filter(item => item.id !== result.id)]);
      setAssetImportDoi("");
      setNotice("已从共用文献库导入论文，并建立个人资料引用。");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "论文导入失败");
    } finally {
      setAssetBusy(false);
    }
  }

  async function importPersonalTask() {
    if (!assetImportTaskId.trim()) return;
    if (!personalProfileVersion) {
      setError("请先保存个人研究画像，再导入研究报告。");
      return;
    }
    setAssetBusy(true);
    setError("");
    try {
      const result = await api<PersonalResearchAsset>("personal-assets/import-task", {
        method: "POST",
        body: JSON.stringify({
          task_id: assetImportTaskId.trim(),
          line_ids: assetDraft.line_ids,
        }),
      });
      setPersonalAssets(current => [result, ...current.filter(item => item.id !== result.id)]);
      setAssetImportTaskId("");
      setNotice("已将研究任务结果快照加入个人资料库。");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "研究报告导入失败");
    } finally {
      setAssetBusy(false);
    }
  }

  async function archivePersonalAsset(assetId: string) {
    setAssetBusy(true);
    setError("");
    try {
      await api("personal-assets/" + assetId, { method: "DELETE" });
      setPersonalAssets(current => current.filter(item => item.id !== assetId));
      setNotice("资料已从当前个人资料库归档；原始论文或报告没有被删除。");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "资料归档失败");
    } finally {
      setAssetBusy(false);
    }
  }

  function toggleAssetLine(lineId: string) {
    setAssetDraft(current => ({
      ...current,
      line_ids: current.line_ids.includes(lineId)
        ? current.line_ids.filter(id => id !== lineId)
        : [...current.line_ids, lineId],
    }));
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
    return <div className={styles.loadingScreen}><Loader2 className={styles.spin} size={22} /><span>正在连接研究空间…<small>首次唤醒认证服务可能需要约 40–60 秒</small></span></div>;
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
            {loginBusy ? <Loader2 className={styles.spin} size={16} /> : null}{loginBusy ? "正在连接认证服务…" : "登录"}
          </button>
        </form>
        <div className={styles.loginFoot}>{teamMode ? "首次连接时，Render 免费后端可能需要约 40–60 秒唤醒。请耐心等待，不要连续重复提交。" : "科研资料按账户权限访问。请勿在公共设备保存登录状态。"}</div>
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
            <div className={styles.modeSwitch}>
              <button className={chatMode === "gpt" ? styles.modeActive : ""} onClick={() => setChatMode("gpt")}>
                GPT 调用 <small>通用对话 · 待接入</small>
              </button>
              <button className={chatMode === "research" ? styles.modeActive : ""} onClick={() => setChatMode("research")}>
                深度研究 <small>Research Agent · 当前可用</small>
              </button>
            </div>
            {chatMode === "gpt" ? <div className={styles.teamChatPending}>
              <div className={styles.pendingIcon}><MessageCircle size={23} /></div>
              <div className={styles.eyebrow}>GPT CONVERSATION</div>
              <h2>通用 GPT 多轮对话尚未接入</h2>
              <p>当前后端提供的是定向 Research Agent 任务接口，尚未提供可持续保存的通用 GPT 对话接口。切换到「深度研究」即可使用现有真实科研任务能力。</p>
              <button className={styles.secondaryButton} onClick={() => setChatMode("research")}>进入深度研究 <ArrowUpRight size={14} /></button>
            </div> : <div className={styles.chatWorkspace}>
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
                  <TaskSourceRunPicker key={selectedTaskId || "new-research"} disabled={!canEdit || busy} onChange={setTaskSourceOverride}/>
                  <div className={styles.composerBottom}>
                    <span>{question.length}/2000 · 每次提交创建一项独立科研任务</span>
                    <button className={styles.primaryButton} type="submit" disabled={!canEdit || busy || question.trim().length < 6}>
                      {busy ? <Loader2 size={15} className={styles.spin} /> : <Send size={15} />}开始研究
                    </button>
                  </div>
                </form>
              </div>
            </div>}
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
          <SourceScopeInline scope={sourceScopes.find(scope => scope.scene === "team_weekly")}
            sources={sourceCatalog} label="团队周报 · 默认期刊"
            onEdit={() => {setSettingsTab("task-sources");changeSection("settings");}}
            missingNote="尚未连接团队周报的专属来源配置" />
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
                <button className={styles.iconAction} onClick={() => downloadReport(displayedWeeklyReport, "research-atlas-team-weekly.md")}
                  disabled={!displayedWeeklyReport} title="下载 Markdown"><Download size={16} /></button>
              </div>
              <SourceScopeInline scope={displayedWeeklyTask?.source_scope}
                sources={sourceCatalog} label="本期周报 · 实际来源快照"
                missingNote={displayedWeeklyTask ? "历史周报未记录来源范围" : "尚无可查看的历史周报"} />
              <ReportBody markdown={displayedWeeklyReport} />
              {displayedWeeklyTask?.status === "running" && <div className={styles.runningState}><Loader2 size={16} className={styles.spin} />周报生成中，完成后会更新报告内容。</div>}
            </article>
            <aside className={styles.historyPanel}>
              <div className={styles.panelHeading}><div><div className={styles.eyebrow}>ARCHIVE</div><h2>历史周报</h2></div><span>{weeklyTasks.length}</span></div>
              {weeklyTasks.length ? weeklyTasks.map(task => <button key={task.id} className={styles.historyItem}
                onClick={() => setSelectedTaskId(task.id)}>
                <span className={styles.historyIcon}><FileText size={15} /></span>
                <span><strong>{shortDate(task.created_at)} · 团队周报</strong><small>{statusText(task.status)} · {sourceScopeShort(task.source_scope)}</small></span>
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
          <SourceScopeInline scope={sourceScopes.find(scope => scope.scene === "personal_weekly")}
            sources={sourceCatalog} label="个人周报 · 我的期刊清单"
            onEdit={() => {setSettingsTab("task-sources");changeSection("settings");}}
            missingNote="尚未连接个人周报来源配置" />
          <div className={styles.personalIntro}>
            <div className={styles.personalIcon}><UserRound size={22} /></div>
            <div><div className={styles.eyebrow}>PERSONAL RESEARCH</div><h2>个人研究动态</h2>
              <p>{personalProfileVersion > 0
                ? `已读取当前账号的个人研究画像（版本 V${personalProfileVersion}），包含 ${personalProfileDraft.research_lines.length} 条研究主线。个人周报生成与独立报告归档仍需后续接入。`
                : "个人研究画像尚未保存。请先到研究设置检查并保存三条个人主线；保存后可用于后续个人周报和定向科研任务匹配。"}
              </p>
              <button className={styles.textButton} type="button" onClick={() => { setSettingsTab("profile"); setSection("settings"); }}>
                {personalProfileVersion > 0 ? "管理个人研究画像" : "检查并保存个人画像"}
              </button>
            </div>
          </div>
          <div className={styles.personalGrid}>
            <div className={styles.personalCard}>
              <span>个人研究画像</span><strong>{personalProfileVersion > 0 ? "已保存" : "待保存"}</strong>
              <p>{personalProfileDraft.research_lines.length} 条主线，账号独立存储。</p>
            </div>
            <div className={styles.personalCard}>
              <span>个性化文献发现</span><strong>待接入</strong><p>后续将按个人主线与个人期刊清单发现论文和方法。</p>
            </div>
            <div className={styles.personalCard}>
              <span>个人报告归档</span><strong>待接入</strong><p>个人周报独立保存，不自动进入团队共享空间。</p>
            </div>
          </div>
          <div className={styles.pendingFootnote}><ShieldCheck size={16} />个人画像的读取与保存已独立于团队画像；个人周报生成和报告归档仍未开放。</div>
        </section>}

        {section === "tasks" && <section>
          <PageHeader eyebrow="SC03 · DIRECTED RESEARCH" title="定向科研任务" description="针对具体研究问题开展文献检索、方法迁移和证据审查，并保存完整研究报告。"
            action={<button className={styles.primaryButton} onClick={() => { setSection("chat"); setChatScope("private"); }}><Plus size={15} />新建任务</button>} />
          <SourceScopeInline scope={sourceScopes.find(scope => scope.scene === "directed_research")}
            sources={sourceCatalog} label="定向科研 · 默认期刊"
            onEdit={() => {setSettingsTab("task-sources");changeSection("settings");}}
            missingNote="尚未连接定向任务来源配置" />
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
                <span className={styles.taskSourceHint}><BookOpen size={12} />{sourceScopeShort(task.source_scope)} · {task.source_scope ? "点击查看清单" : "未记录清单"}</span>
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
                <SourceScopeInline scope={selectedTask.source_scope} sources={sourceCatalog}
                  label="本次任务 · 期刊清单快照"
                  missingNote="该历史任务未记录专属来源快照，不能推断其当时限制了哪些期刊" />
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
              <button className={settingsTab === "task-sources" ? styles.settingsTabActive : ""} onClick={() => setSettingsTab("task-sources")}><SlidersHorizontal size={16} />任务期刊清单</button>
              <button className={settingsTab === "sources" ? styles.settingsTabActive : ""} onClick={() => setSettingsTab("sources")}><BookOpen size={16} />来源总目录</button>
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
                <div className={styles.panelHeading}>
                  <div><div className={styles.eyebrow}>PERSONAL PROFILE · PRIVATE TO THIS ACCOUNT</div><h2>个人研究画像</h2></div>
                  <span className={personalProfileVersion ? styles.versionLabel : styles.pendingLabel}>
                    {personalProfileLoaded ? (personalProfileVersion ? `个人版本 V${personalProfileVersion}` : "尚未保存") : "连接中"}
                  </span>
                </div>
                <p className={styles.settingsDescription}>仅当前登录账号可读取和修改。个人画像与团队共享画像分开保存；下方三条主线已预填，可检查后保存到你的账号。</p>
                {!personalProfileLoaded ? (
                  <div className={styles.inlineError}><AlertCircle size={15} />个人画像接口暂不可用。请确认后端已更新并刷新页面；不会将内容写入团队画像。</div>
                ) : <>
                  <label className={styles.fullField}>个人研究目标
                    <textarea rows={3} value={personalProfileDraft.goals}
                      onChange={event => setPersonalProfileDraft(current => ({ ...current, goals: event.target.value }))} />
                  </label>
                  <label className={styles.fullField}>方法基础
                    <textarea rows={3} value={personalProfileDraft.methods.join("\n")}
                      onChange={event => setPersonalProfileDraft(current => ({
                        ...current, methods: event.target.value.split("\n").map(x => x.trim()).filter(Boolean),
                      }))} />
                  </label>
                  <div className={styles.sectionSubhead}><h3>个人研究主线</h3><span>{personalProfileDraft.research_lines.length} 条</span></div>
                  {personalProfileDraft.research_lines.map((line, index) => {
                    const linkedEvidence = personalProfileDraft.evidence.filter(item => item.line_id === line.id);
                    return <div className={styles.lineEditor} key={line.id}>
                      <div className={styles.lineEditorTop}>
                        <strong>个人主线 {index + 1}</strong>
                        <button onClick={() => removePersonalResearchLine(index)} type="button" aria-label="删除个人研究主线"><X size={15} /></button>
                      </div>
                      <label>名称<input value={line.name} onChange={event => updatePersonalResearchLine(index, { name: event.target.value })} /></label>
                      <label>核心问题<textarea rows={3} value={line.problem} onChange={event => updatePersonalResearchLine(index, { problem: event.target.value })} /></label>
                      <label>关键词<textarea rows={2} value={line.keywords.join("\n")}
                        onChange={event => updatePersonalResearchLine(index, { keywords: event.target.value.split("\n").map(x => x.trim()).filter(Boolean) })} /></label>
                      <div className={styles.formGrid}>
                        <label>问题检索词<textarea rows={3} value={line.search_queries.join("\n")}
                          onChange={event => updatePersonalResearchLine(index, { search_queries: event.target.value.split("\n").map(x => x.trim()).filter(Boolean) })} /></label>
                        <label>方法检索词<textarea rows={3} value={line.method_queries.join("\n")}
                          onChange={event => updatePersonalResearchLine(index, { method_queries: event.target.value.split("\n").map(x => x.trim()).filter(Boolean) })} /></label>
                      </div>
                      {linkedEvidence.length > 0 && <div className={styles.personalEvidenceList}>
                        <span>关联论文与研究报告</span>
                        {linkedEvidence.map(item => <a key={item.id} href={item.url} target="_blank" rel="noreferrer">
                          <span>{item.title}</span><ArrowUpRight size={13} />
                          {item.note && <small>{item.note}</small>}
                        </a>)}
                      </div>}
                    </div>;
                  })}
                  <div className={styles.profileActions}>
                    <button className={styles.secondaryButton} type="button" onClick={addPersonalResearchLine}><Plus size={14} />添加个人主线</button>
                    <button className={styles.primaryButton} type="button" onClick={() => void savePersonalProfile()} disabled={busy}>
                      <Check size={15} />{personalProfileVersion ? "保存个人画像" : "保存到我的账号"}
                    </button>
                  </div>
                </>}
              </section>

              <section className={styles.settingsCard}>
                <div className={styles.panelHeading}><div><div className={styles.eyebrow}>REPORT SCHEDULE</div><h2>周报周期</h2></div><span className={styles.pendingLabel}>网页端暂未开放</span></div>
                <p className={styles.settingsDescription}>当前周报由服务端计划任务和 Worker 配置驱动。网页端尚未提供周期修改接口，因此此处只展示配置状态，不提供无效开关。</p>
              </section>
            </div>}

            {settingsTab === "task-sources" && <div className={styles.settingsContent}><TaskSourceScopeSettings canAdmin={canAdmin} canEdit={canEdit}
              onSaved={scope => setSourceScopes(current =>
                current.some(item => item.scene === scope.scene)
                  ? current.map(item => item.scene === scope.scene ? scope : item)
                  : [...current, scope]
              )} /></div>}
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
