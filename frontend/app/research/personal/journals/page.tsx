import {notFound,redirect} from "next/navigation";
import {getTeamToken,teamAuthEnabled} from "@/lib/session";
import VenueRadar from "./venue-radar";

export const runtime="nodejs";
export const dynamic="force-dynamic";

export default async function ChildHealthJournalRadarPage(){
  if(!teamAuthEnabled())notFound();
  const token=await getTeamToken();
  if(!token)redirect("/devstudio");
  const base=process.env.BACKEND_URL,key=process.env.API_BEARER_TOKEN;
  if(!base||!key)notFound();
  try{
    const response=await fetch(base.replace(/\/$/,"")+"/api/auth/me",{
      cache:"no-store",signal:AbortSignal.timeout(12000),
      headers:{"Authorization":"Bearer "+key,"X-Research-Session":token},
    });
    if(response.status===401)redirect("/devstudio");
    if(!response.ok)notFound();
    const data=await response.json();
    if(!data.member?.id)notFound();
    return <VenueRadar/>;
  }catch(e){
    if(e&&typeof e==="object"&&"digest" in e)throw e;
    notFound();
  }
}
