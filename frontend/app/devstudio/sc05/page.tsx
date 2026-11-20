import { notFound, redirect } from "next/navigation";
import { getTeamToken, teamAuthEnabled } from "@/lib/session";
import SC05Console from "./sc05-console";

export const runtime="nodejs";
export const dynamic="force-dynamic";

/** Owner-only web management of real SC05 A/B experiments. */
export default async function SC05ConsolePage() {
  if (!teamAuthEnabled()) notFound();
  const token=await getTeamToken();
  if (!token) redirect("/devstudio");
  const base=process.env.BACKEND_URL;
  const bearer=process.env.API_BEARER_TOKEN;
  if (!base || !bearer) notFound();
  let response:Response;
  try {
    response=await fetch(base.replace(/\/$/,"")+"/api/auth/me",{
      cache:"no-store",signal:AbortSignal.timeout(12000),
      headers:{"Authorization":"Bearer "+bearer,"X-Research-Session":token},
    });
  } catch {notFound();}
  if (response.status===401) redirect("/devstudio");
  if (!response.ok) notFound();
  const payload=await response.json();
  if (payload.member?.role!=="owner" || payload.member?.active===false) notFound();
  return <SC05Console />;
}
