/** Server-only GitHub Actions launcher for the private research workflow.
 *
 * A fine-grained repo-scoped Actions write token is NEVER returned to browser.
 * The user must have a valid team session with role=admin.
 */
import "server-only";
import {authenticated,getTeamToken,teamAuthEnabled} from "@/lib/session";

export const workflowUrl =
 "https://github.com/Hu-py/research-agent-lab/actions/workflows/live-frontier.yml";
const apiBase =
 "https://api.github.com/repos/Hu-py/research-agent-lab/actions/workflows/live-frontier.yml";
type Denied={ok:false;status:number;detail:string};
type Granted={ok:true};
export type AuthResult=Denied|Granted;
export const privateResponseHeaders={
 "Cache-Control":"private, no-store",
 "X-Robots-Tag":"noindex, nofollow"
};

export async function adminGate():Promise<AuthResult>{
  if(!teamAuthEnabled())return {
    ok:false,status:403,detail:"付费实验启动只对已启用团队登录的管理员开放"
  };
  if(!(await authenticated()))return {ok:false,status:401,detail:"请先登录科研工作台"};
  const token=await getTeamToken();
  const backend=process.env.BACKEND_URL||"";
  const apiKey=process.env.API_BEARER_TOKEN||"";
  if(!token||!backend.startsWith("https://")||!apiKey)return {
    ok:false,status:503,detail:"团队权限验证服务未就绪"
  };
  try{
    const r=await fetch(backend.replace(/\/$/,"")+"/api/auth/me",{
      cache:"no-store",redirect:"manual",signal:AbortSignal.timeout(9000),
      headers:{"Authorization":"Bearer "+apiKey,"X-Research-Session":token}
    });
    if(!r.ok)return {ok:false,status:401,detail:"团队登录已过期，请重新登录"};
    const member=(await r.json())?.member;
    if(!member?.id||member?.role!=="admin"||member?.active===false){
      return {ok:false,status:403,detail:"仅团队管理员可以发起付费科研实验"};
    }
    return {ok:true};
  }catch{
    return {ok:false,status:503,detail:"暂时无法验证团队管理员身份"};
  }
}

export function launchConfigured():boolean{
  return Boolean((process.env.RESEARCH_LAB_GITHUB_TOKEN||"").trim().length>20);
}
function config(){
  const token=(process.env.RESEARCH_LAB_GITHUB_TOKEN||"").trim();
  if(token.length<21)throw Error("LAUNCH_TOKEN_MISSING");
  return {"Authorization":"Bearer "+token,
    "Accept":"application/vnd.github+json",
    "X-GitHub-Api-Version":"2022-11-28"
  };
}
export type LaunchInput={
 evidence_source:"workbench_sync"|"public_demo"|"team_evidence"|"approved_secret";
 max_generations:"0"|"1"|"2";
 max_papers:"4"|"6"|"8";
 max_pairs:"1"|"2"|"3";
 stream_live_events:boolean;
 synthetic_pilot:boolean;
 reuse_llm_cache:boolean;
 replay_namespace:string;
 save_knowledge_graph:boolean;
 bilingual_report:boolean;
};
const allowedKeys=new Set([
 "evidence_source","max_generations","max_papers","max_pairs",
 "stream_live_events","synthetic_pilot","reuse_llm_cache","replay_namespace",
 "save_knowledge_graph","bilingual_report"
]);
function oneOf<T extends string>(v:unknown,options:readonly T[]):v is T{
 return typeof v==="string"&&options.includes(v as T);
}
export function validateLaunch(raw:unknown):LaunchInput{
 if(!raw||typeof raw!=="object"||Array.isArray(raw))throw Error("INVALID_PARAMETERS");
 const x=raw as Record<string,unknown>;
 if(Object.keys(x).length!==allowedKeys.size||
    Object.keys(x).some(k=>!allowedKeys.has(k)))throw Error("INVALID_PARAMETERS");
 if(!oneOf(x.evidence_source,["workbench_sync","public_demo","team_evidence","approved_secret"])||
    !oneOf(x.max_generations,["0","1","2"])||
    !oneOf(x.max_papers,["4","6","8"])||
    !oneOf(x.max_pairs,["1","2","3"])){
   throw Error("INVALID_PARAMETERS");
 }
 for(const field of [
  "stream_live_events","synthetic_pilot","reuse_llm_cache",
  "save_knowledge_graph","bilingual_report"
 ]){
   if(typeof x[field]!=="boolean")throw Error("INVALID_PARAMETERS");
 }
 if(typeof x.replay_namespace!=="string"||
    !/^[a-zA-Z0-9_-]{1,64}$/.test(x.replay_namespace)){
   throw Error("INVALID_NAMESPACE");
 }
 if(x.save_knowledge_graph &&
    !["workbench_sync","team_evidence"].includes(x.evidence_source)){
   throw Error("GRAPH_REQUIRES_TEAM_EVIDENCE");
 }
 // This workflow always saves to the dedicated lab Supabase project.
 return x as LaunchInput;
}
function toInputs(x:LaunchInput):Record<string,string>{
 return {
   evidence_source:x.evidence_source,
   max_generations:x.max_generations,
   max_papers:x.max_papers,
   max_pairs:x.max_pairs,
   stream_live_events:String(x.stream_live_events),
   synthetic_pilot:String(x.synthetic_pilot),
   reuse_llm_cache:String(x.reuse_llm_cache),
   replay_namespace:x.replay_namespace,
   save_knowledge_graph:String(x.save_knowledge_graph),
   bilingual_report:String(x.bilingual_report)
 };
}
export type RemoteRun={
 id:number;status:string;conclusion:string|null;created_at:string;
 html_url:string;display_title:string;run_number:number
};
async function githubFetch(url:string,init?:RequestInit):Promise<Response>{
 const response=await fetch(url,{
   ...init,cache:"no-store",redirect:"manual",
   signal:AbortSignal.timeout(14000),
   headers:{...config(),...(init?.headers||{})}
 });
 if(!response.ok){
   if(response.status===401||response.status===403)throw Error("GITHUB_PERMISSION_DENIED");
   if(response.status===404)throw Error("GITHUB_WORKFLOW_NOT_FOUND");
   throw Error("GITHUB_HTTP_"+response.status);
 }
 return response;
}

export async function recentLaunches():Promise<RemoteRun[]>{
 const response=await githubFetch(apiBase+"/runs?event=workflow_dispatch&per_page=20");
 const data=await response.json();
 if(!Array.isArray(data?.workflow_runs))throw Error("GITHUB_INVALID_RESPONSE");
 return data.workflow_runs.map((r:Record<string,unknown>)=>({
   id:Number(r.id||0),status:String(r.status||"unknown"),
   conclusion:typeof r.conclusion==="string"?r.conclusion:null,
   created_at:String(r.created_at||""),html_url:String(r.html_url||""),
   display_title:String(r.display_title||"Research Lab"),
   run_number:Number(r.run_number||0)
 })).filter((x:RemoteRun)=>
   x.id>0&&/^https:\/\/github\.com\/Hu-py\/research-agent-lab\/actions\/runs\/\d+$/.test(x.html_url));
}

export async function dispatchLaunch(payload:LaunchInput){
 const existing=await recentLaunches();
 const busy=existing.some(r=>
   ["queued","in_progress","requested","waiting","pending"].includes(r.status));
 if(busy)throw Error("EXPERIMENT_ALREADY_RUNNING");
 await githubFetch(apiBase+"/dispatches",{
   method:"POST",headers:{"Content-Type":"application/json"},
   body:JSON.stringify({ref:"main",inputs:toInputs(payload)})
 });
 return {status:"accepted",workflow_url:workflowUrl,
   max_model_calls:(payload.max_generations==="2"?55:30)
     +(payload.bilingual_report?1:0),
   initiated_at:new Date().toISOString()};
}
