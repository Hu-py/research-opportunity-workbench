/* Preview-only E2E bridge probe. Never merge this test route into main.
 * It has no public-use functionality unless explicitly enabled by a
 * branch-scoped server-side secret, and targets only the isolated Render API.
 */
import { createHash, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

export const runtime="nodejs";
export const dynamic="force-dynamic";
const ISOLATED="https://research-atlas-devstudio-e2e-ejmh.onrender.com";
const TITLE="Preview UI -> Next Proxy -> Render Postgres E2E 2026-11-14";

function equal(a:string,b:string):boolean {
  const x=createHash("sha256").update(a).digest();
  const y=createHash("sha256").update(b).digest();
  return timingSafeEqual(x,y);
}
function json(value:unknown,status=200) {
  return NextResponse.json(value,{status,headers:{"Cache-Control":"no-store","X-Robots-Tag":"noindex, nofollow"}});
}
export async function GET(request:NextRequest) {
  if (process.env.VERCEL_ENV!=="preview" ||
      process.env.DEVSTUDIO_E2E_PREVIEW!=="1")
    return json({detail:"Not found"},404);
  const expected=process.env.DEVSTUDIO_E2E_PROBE_KEY||"";
  const supplied=request.nextUrl.searchParams.get("probe")||"";
  if(expected.length<32 || !equal(supplied,expected))
    return json({detail:"Not found"},404);
  if(process.env.BACKEND_URL?.replace(/\/$/,"")!==ISOLATED ||
     !process.env.API_BEARER_TOKEN ||
     !process.env.DEVSTUDIO_BROWSER_TEST_PASSWORD)
    return json({status:"BLOCKED",stage:"isolation_or_configuration"},503);

  const checks:{name:string;code:number;passed:boolean}[]=[];
  try {
    // Prove real Backend authentication with the scoped fixture.
    const login=await fetch(ISOLATED+"/api/auth/login",{
      method:"POST",cache:"no-store",signal:AbortSignal.timeout(25000),
      headers:{"Content-Type":"application/json",
               "Authorization":"Bearer "+process.env.API_BEARER_TOKEN},
      body:JSON.stringify({
        email:process.env.DEVSTUDIO_BROWSER_TEST_EMAIL,
        password:process.env.DEVSTUDIO_BROWSER_TEST_PASSWORD,
      }),
    });
    checks.push({name:"backend_admin_login",code:login.status,passed:login.ok});
    if(!login.ok)return json({status:"FAIL",stage:"backend_admin_login",checks},502);
    const data=await login.json();
    const memberToken=data?.token;
    if(typeof memberToken!=="string"||data?.member?.role!=="admin")
      return json({status:"FAIL",stage:"test_admin_role",checks},502);

    // Request the *real* Next.js proxy route with the team's signed session.
    // Preserve protection-cookie context from the Vercel request if present.
    const cookie="research_member_session="+encodeURIComponent(memberToken)+
      (request.headers.get("cookie")?"; "+request.headers.get("cookie"):"");
    const origin=request.nextUrl.origin;
    const throughProxy=async(path:string,payload?:unknown)=>{
      const res=await fetch(new URL("/api/proxy/devstudio/"+path,origin),{
        method:payload===undefined?"GET":"POST",cache:"no-store",
        redirect:"manual",signal:AbortSignal.timeout(30000),
        headers:{"Cookie":cookie,"Content-Type":"application/json"},
        ...(payload===undefined?{}:{body:JSON.stringify(payload)}),
      });
      const ct=res.headers.get("content-type")||"";
      const body=ct.includes("json")?await res.json().catch(()=>null):null;
      return {status:res.status,body,ct};
    };
    const first=await throughProxy("experiments");
    checks.push({name:"next_proxy_initial_list",code:first.status,passed:first.status===200});
    if(first.status!==200||!Array.isArray(first.body?.items))
      return json({status:"FAIL",stage:"next_proxy_initial_list",checks},502);
    let record=first.body.items.find((v:{title?:string})=>v.title===TITLE);
    if(!record){
      const created=await throughProxy("experiments",{
        module_id:"PLATFORM",
        title:TITLE,
        hypothesis:"A preview-only Next.js proxy persists a test experiment to isolated PostgreSQL.",
        baseline:"Previous Render E2E verified backend only.",
        input_snapshot_ref:"experiment/devstudio-postgres-e2e-20261114",
        metrics:["proxy_create","proxy_read_after_refresh"],
      });
      checks.push({name:"next_proxy_create",code:created.status,passed:created.status===201});
      if(created.status!==201 || typeof created.body?.id!=="string")
        return json({status:"FAIL",stage:"next_proxy_create",checks},502);
      record=created.body;
    }else{
      checks.push({name:"next_proxy_existing_record",code:200,passed:true});
    }
    const refreshed=await throughProxy("experiments");
    const found=refreshed.status===200 &&
      refreshed.body?.items?.some((v:{id?:string;title?:string})=>v.id===record.id&&v.title===TITLE);
    checks.push({name:"next_proxy_second_read",code:refreshed.status,passed:found});
    if(!found)return json({status:"FAIL",stage:"next_proxy_second_read",checks},502);

    const html=await fetch(new URL("/devstudio",origin),{
      cache:"no-store",redirect:"manual",signal:AbortSignal.timeout(30000),
      headers:{"Cookie":cookie},
    });
    const markup=await html.text();
    const authorized=html.status===200 &&
      markup.includes("loadDevStudio()") && markup.includes("Development Studio");
    checks.push({name:"next_authenticated_devstudio_html",code:html.status,passed:authorized});

    return json({
      status:checks.every(x=>x.passed)?"PASS":"PARTIAL",
      record_id:record.id,
      checks,
      note:"Server-side E2E only; does not execute JavaScript clicks in a browser.",
    },checks.every(x=>x.passed)?200:502);
  }catch(error){
    return json({status:"FAIL",stage:"network_or_server_exception",checks,
      detail:error instanceof Error?error.name:"UnknownError"},502);
  }
}
