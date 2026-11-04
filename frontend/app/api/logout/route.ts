import { NextResponse } from "next/server";
import { getTeamToken, removeSession, removeTeamToken, teamAuthEnabled } from "@/lib/session";
export async function POST() {
  if(teamAuthEnabled()){
    const token=await getTeamToken(),base=process.env.BACKEND_URL,key=process.env.API_BEARER_TOKEN;
    if(token && base && key){
      try{
        await fetch(base.replace(/\/$/,"")+"/api/auth/logout",{
          method:"POST",cache:"no-store",signal:AbortSignal.timeout(8000),
          headers:{"Authorization":"Bearer "+key,"X-Research-Session":token}
        });
      }catch{/* Revoke server-side session on reconnect/expiry; clear local cookie now. */}
    }
    await removeTeamToken();
  }
  await removeSession();
  return NextResponse.json({ok:true});
}
