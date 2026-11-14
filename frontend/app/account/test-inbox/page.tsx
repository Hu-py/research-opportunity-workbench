import { notFound, redirect } from "next/navigation";
import { getTeamToken, teamAuthEnabled } from "@/lib/session";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type SimulatedMessage = {
  recipient: string;
  subject: string;
  kind: string;
  link: string;
  received_at: number;
  expires_at: number;
};
type Inbox = { mode: string; real_email_verified: boolean; notice: string; items: SimulatedMessage[] };

export default async function TestInbox() {
  if (process.env.VERCEL_ENV !== "preview" || !teamAuthEnabled()) notFound();
  const backend = process.env.BACKEND_URL?.replace(/\/$/, "") || "";
  if (backend !== "https://research-atlas-devstudio-e2e-ejmh.onrender.com") notFound();
  const token = await getTeamToken();
  if (!token) redirect("/devstudio");
  const key = process.env.API_BEARER_TOKEN;
  if (!key) notFound();
  const response = await fetch(backend + "/api/account/test-inbox", {
    cache: "no-store",
    headers: { "Authorization": "Bearer " + key, "X-Research-Session": token },
    signal: AbortSignal.timeout(15000),
  });
  if (response.status === 401) redirect("/devstudio");
  if (!response.ok) notFound();
  const inbox = (await response.json()) as Inbox;
  if (inbox.mode !== "SIMULATED" || inbox.real_email_verified !== false) notFound();
  return (
    <main style={{ padding:"36px 22px", maxWidth:850, margin:"auto",
                   fontFamily:"system-ui, sans-serif", lineHeight:1.6 }}>
      <p style={{ color:"#777",fontSize:12 }}>RESEARCH ATLAS / ISOLATED E2E ONLY</p>
      <h1 style={{fontSize:25}}>模拟收件箱（测试模式）</h1>
      <p role="alert" style={{padding:"12px 14px",background:"#f5f5f5",fontSize:14}}>
        不会发送真实邮件，也不验证真实邮箱所有权。
        所有模拟账号仅存在于隔离测试数据库，不可用于正式环境。
      </p>
      <p>测试 Owner 邮箱：<code>owner-sandbox@research-atlas.invalid</code></p>
      <p>
        <a href="/account/setup">申请测试 Owner 链接</a>
        {" · "}
        <a href="/account/team">团队邀请管理</a>
        {" · "}
        <a href="/devstudio">返回开发者中心</a>
      </p>
      <h2 style={{fontSize:17}}>最新模拟验证邮件</h2>
      {inbox.items.length === 0 ? (
        <p>还没有模拟邮件。先去 Owner 开通页面发送验证请求，然后刷新本页面。</p>
      ) : (
        <ul style={{listStyle:"none",padding:0}}>
          {inbox.items.map((m,i)=>(
            <li key={i} style={{border:"1px solid #ddd",borderRadius:7,padding:18,marginBottom:12}}>
              <div><strong>{m.subject}</strong></div>
              <div style={{fontSize:12,color:"#666"}}>收件人：{m.recipient}</div>
              <div style={{fontSize:12,color:"#666"}}>类型：{m.kind}；有效至：
                {new Date(m.expires_at*1000).toLocaleString("zh-CN")}
              </div>
              <a href={m.link} style={{display:"inline-block",marginTop:12,
                  background:"#111",color:"#fff",padding:"9px 14px",borderRadius:5,
                  textDecoration:"none"}}>打开模拟验证链接</a>
            </li>
          ))}
        </ul>
      )}
      <p style={{fontSize:12,color:"#777"}}>
        模拟验证链接保存在单个测试服务实例的内存中，服务重启后可能消失。
        这不影响已保存的测试账号，但需要重新申请未使用的链接。
      </p>
    </main>
  );
}
