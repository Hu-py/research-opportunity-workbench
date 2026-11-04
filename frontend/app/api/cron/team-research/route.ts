import {NextRequest,NextResponse} from "next/server";
import {timingSafeEqual} from "node:crypto";

// Vercel Hobby Cron invokes GET once per day. Server-side keys never reach the browser.
export const dynamic="force-dynamic";
export const maxDuration=60;

function constantEqual(a:string,b:string){
  const one=Buffer.from(a);const two=Buffer.from(b);
  return one.length===two.length && timingSafeEqual(one,two);
}

export async function GET(request:NextRequest){
  const secret=process.env.CRON_SECRET;
  if(!secret || secret.length<24 ||
     !constantEqual(request.headers.get("authorization")||"","Bearer "+secret)){
    return NextResponse.json({detail:"Unauthorized cron invocation"},{status:401});
  }
  const base=process.env.BACKEND_URL;
  const apiToken=process.env.API_BEARER_TOKEN;
  const syncSecret=process.env.ATLAS_SYNC_SECRET;
  if(!base||!/^https:\/\//.test(base)||!apiToken||!syncSecret){
    return NextResponse.json({detail:"Research sync is not configured"},{status:503});
  }
  try{
    const response=await fetch(base.replace(/\/$/,"")+"/api/team-repository/refresh-scheduled",{
      method:"POST",
      redirect:"manual",
      cache:"no-store",
      headers:{
        "Content-Type":"application/json",
        "Authorization":"Bearer "+apiToken,
        "X-Atlas-Sync-Secret":syncSecret,
      },
      signal:AbortSignal.timeout(45000),
    });
    if(!response.ok){
      return NextResponse.json({ok:false,upstream_status:response.status},{status:502});
    }
    const data=await response.json();
    return NextResponse.json({ok:true,queued:true,run_id:data.id},{status:202});
  }catch{
    return NextResponse.json({ok:false,detail:"Unable to reach research API"},{status:502});
  }
}
