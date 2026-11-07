/** Server-only read access to the isolated Research Agent Lab Supabase project.
 * No keys, raw data, or service-role credentials ever reach the browser.
 */
import "server-only";
import { authenticated, getTeamToken, teamAuthEnabled } from "@/lib/session";

type Gate = { ok:true } | { ok:false; status:number; detail:string };
const privateHeaders={"Cache-Control":"private, no-store","X-Robots-Tag":"noindex, nofollow"};
export {privateHeaders};

export async function sessionGate():Promise<Gate> {
  if (!(await authenticated()))return {ok:false,status:401,detail:"请先登录科研工作台"};
  if (!teamAuthEnabled())return {ok:true};
  const token=await getTeamToken();
  const base=process.env.BACKEND_URL||"";
  const key=process.env.API_BEARER_TOKEN||"";
  if(!token||!base||!key)return {ok:false,status:401,detail:"团队登录状态不可用，请重新登录"};
  try {
    const response=await fetch(base.replace(/\/$/,"")+"/api/auth/me",{
      cache:"no-store",redirect:"manual",signal:AbortSignal.timeout(10000),
      headers:{"Authorization":"Bearer "+key,"X-Research-Session":token}
    });
    if(!response.ok)return {ok:false,status:401,detail:"团队会话已失效，请重新登录"};
    const result=await response.json();
    if(!result?.member?.id)return {ok:false,status:401,detail:"团队登录验证失败"};
    return {ok:true};
  } catch {
    return {ok:false,status:503,detail:"无法验证团队权限，请检查工作台后端"};
  }
}

function labConfig():{base:string;key:string}|null {
  const value=(process.env.RESEARCH_LAB_SUPABASE_URL||"").trim().replace(/\/$/,"");
  const secret=(process.env.RESEARCH_LAB_SUPABASE_SECRET_KEY||"").trim();
  let url:URL;
  try{url=new URL(value);}catch{return null;}
  if(url.protocol!=="https:"||!/^[a-z0-9-]+\.supabase\.co$/.test(url.hostname)||
     url.pathname!=="/"||url.search||url.hash||url.username||url.password||url.port)return null;
  if(!(secret.startsWith("sb_secret_")||
       (secret.startsWith("eyJ")&&secret.split(".").length===3)))return null;
  return {base:value,key:secret};
}
export function configured():boolean{return labConfig()!==null;}

export async function labRead(
  params:Record<string,string>,
  table:"lab_frontier_runs"|"lab_frontier_events"="lab_frontier_runs"
):Promise<unknown> {
  const conf=labConfig();
  if(!conf)throw new Error("LAB_NOT_CONFIGURED");
  const query=new URLSearchParams(params);
  const headers:Record<string,string>={"apikey":conf.key,"Accept":"application/json"};
  // Modern sb_secret keys are NOT JWTs; do not send Bearer for these.
  if(!conf.key.startsWith("sb_secret_"))headers.Authorization="Bearer "+conf.key;
  let response:Response;
  try {
    response=await fetch(conf.base+"/rest/v1/"+table+"?"+query.toString(),{
      cache:"no-store",redirect:"manual",signal:AbortSignal.timeout(18000),headers
    });
  }catch{throw new Error("LAB_CONNECTION_FAILED");}
  if(!response.ok)throw new Error("LAB_HTTP_"+response.status);
  const content=await response.json();
  if(!Array.isArray(content))throw new Error("LAB_UNEXPECTED_RESPONSE");
  return content;
}

export function safeListItem(row:Record<string,unknown>) {
  const result=row.results&&typeof row.results==="object"&&!Array.isArray(row.results)?
    row.results as Record<string,unknown>:{};
  return {
    id:String(row.id||""),line_id:String(row.line_id||""),
    status:String(row.status||""),strategy:String(row.strategy||""),
    created_at:String(row.created_at||""),
    model_calls:Number(row.model_calls||0),
    provider_calls:Number(result.provider_calls??row.model_calls??0),
    winner_title:String(result.winner_title||""),
    generation_count:Number(result.generation_count||0),
    match_count:Array.isArray(result.matches)?result.matches.length:0
  };
}

export function safeDetail(row:Record<string,unknown>) {
  const r=row.results&&typeof row.results==="object"&&!Array.isArray(row.results)?
    row.results as Record<string,unknown>:{};
  // Field allow-list prevents accidental exposure of future raw-data columns.
  const allow=[
    "winner_id","winner_title","generation_count","lineage","verification","pilot",
    "paper_ids","ranked_candidates","archived_candidates","matches",
    "supervisor_decisions","screening","knowledge","event_log","comparison_context",
    "cache_hits","provider_calls","human_review_required","bilingual_report"
  ];
  const result:Record<string,unknown>={};
  for(const key of allow)if(Object.prototype.hasOwnProperty.call(r,key))result[key]=r[key];
  return {...safeListItem(row),results:result};
}
