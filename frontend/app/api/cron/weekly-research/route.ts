import {NextRequest,NextResponse} from "next/server";
import {timingSafeEqual} from "node:crypto";

export const dynamic="force-dynamic";
export const maxDuration=60;

function equal(a:string,b:string){
 const one=Buffer.from(a);const two=Buffer.from(b);
 return one.length===two.length && timingSafeEqual(one,two);
}
export async function GET(request:NextRequest){
 const secret=process.env.CRON_SECRET;
 if(!secret||secret.length<24||!equal(request.headers.get("authorization")||"","Bearer "+secret))
   return NextResponse.json({detail:"Unauthorized cron invocation"},{status:401});
 const base=process.env.BACKEND_URL;
 const bearer=process.env.API_BEARER_TOKEN;
 const sync=process.env.ATLAS_SYNC_SECRET;
 if(!base||!/^https:\/\//.test(base)||!bearer||!sync)
   return NextResponse.json({detail:"Weekly research sync is not configured"},{status:503});
 try{
   const response=await fetch(base.replace(/\/$/,"")+"/api/radar/weekly-scheduled",{
     method:"POST",redirect:"manual",cache:"no-store",
     headers:{"Content-Type":"application/json","Authorization":"Bearer "+bearer,"X-Atlas-Sync-Secret":sync},
     signal:AbortSignal.timeout(45000),
   });
   if(!response.ok)
     return NextResponse.json({ok:false,upstream_status:response.status},{status:502});
   return NextResponse.json(await response.json(),{status:202});
 }catch{
   return NextResponse.json({ok:false,detail:"Unable to reach research API"},{status:502});
 }
}
