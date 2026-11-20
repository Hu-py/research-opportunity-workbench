import { notFound, redirect } from "next/navigation";
import { getTeamToken, teamAuthEnabled } from "@/lib/session";
import TeamManagement from "./team-management";

export const runtime="nodejs";
export const dynamic="force-dynamic";

export default async function Page() {
  if(!teamAuthEnabled())notFound();
  const token=await getTeamToken();
  if(!token)redirect("/devstudio");
  const base=process.env.BACKEND_URL;
  const secret=process.env.API_BEARER_TOKEN;
  if(!base||!secret)notFound();
  try {
    const response=await fetch(base.replace(/\/$/,"")+"/api/auth/me",{
      cache:"no-store",signal:AbortSignal.timeout(12000),
      headers:{"Authorization":"Bearer "+secret,"X-Research-Session":token},
    });
    if(!response.ok)redirect("/devstudio");
    const data=await response.json();
    if(!["owner","admin"].includes(data.member?.role))notFound();
    return <TeamManagement currentRole={data.member.role} />;
  } catch(err) {
    if (err && typeof err==="object" && "digest" in err) throw err;
    notFound();
  }
}
