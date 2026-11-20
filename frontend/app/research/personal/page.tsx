import { notFound, redirect } from "next/navigation";
import {getTeamToken,teamAuthEnabled} from "@/lib/session";
import PersonalResearch from "./personal-research";

export const runtime="nodejs";
export const dynamic="force-dynamic";

export default async function PersonalResearchPage(){
  if(!teamAuthEnabled())notFound();
  const token=await getTeamToken();
  if(!token)redirect("/devstudio");
  const base=process.env.BACKEND_URL;
  const bearer=process.env.API_BEARER_TOKEN;
  if(!base||!bearer)notFound();
  try {
    const res=await fetch(base.replace(/\/$/,"")+"/api/auth/me",{
      cache:"no-store",signal:AbortSignal.timeout(12000),
      headers:{"Authorization":"Bearer "+bearer,"X-Research-Session":token},
    });
    if(res.status===401)redirect("/devstudio");
    if(!res.ok)notFound();
    const result=await res.json();
    if(!result.member?.id)notFound();
    return <PersonalResearch/>;
  }catch(e){
    if(e&&typeof e==="object"&&"digest" in e)throw e;
    notFound();
  }
}
