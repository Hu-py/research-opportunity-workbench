import {NextResponse} from "next/server";
import {configured,labRead,privateHeaders,sessionGate} from "@/lib/research-lab-server";

export const dynamic="force-dynamic";
const stages = new Set([
 "run_started","run_completed","run_failed","feasibility_gate",
 "feasibility_revision","no_recommendation","knowledge_discovery",
 "independent_paper_screen","generate","elo_tournament","supervisor",
 "hypothesis_evolution","hypothesis_expansion","rollback","scientific_gate"
]);
export async function GET(){
 const gate=await sessionGate();
 if(!gate.ok)return NextResponse.json({detail:gate.detail},
   {status:gate.status,headers:privateHeaders});
 if(!configured())return NextResponse.json({
   configured:false,enabled:false,items:[],
   detail:"独立实验库的服务端密钥尚未配置，无法读取实时事件。"
 },{headers:privateHeaders});
 try {
   const rows=await labRead({
     select:"run_id,step_index,stage,details,recorded_at",
     order:"recorded_at.desc",limit:"150"
   },"lab_frontier_events") as Record<string,unknown>[];
   const items=rows.filter(r=>typeof r.stage==="string"&&stages.has(r.stage))
     .map(row=>{
       const d=(row.details&&typeof row.details==="object"&&!Array.isArray(row.details)?
         row.details:{}) as Record<string,unknown>;
       const details:Record<string,unknown>={};
       for(const key of ["generation","retrieved","retained","disagreements",
                         "matches","archived_generation","created_count","children_count",
                         "eligible_count","blocked_count","revision_attempt","rejected_count"]){
         if(Number.isInteger(d[key])&&Number(d[key])>=0)details[key]=d[key];
       }
       for(const key of ["pilot_executed","data_feasible_assessment","no_valid_children"]){
         if(typeof d[key]==="boolean")details[key]=d[key];
       }
       for(const key of ["leader","winner"]){
         if(typeof d[key]==="string"&&/^H[0-9]{1,6}$/.test(d[key]))details[key]=d[key];
       }
       if(typeof d.failure_code==="string" && [
         "CANDIDATE_SCHEMA_INVALID","MODEL_BUDGET_EXHAUSTED",
         "MODEL_PROVIDER_ERROR","EVIDENCE_PIPELINE_ERROR",
         "SCIENTIFIC_GATE_ERROR","OTHER_RUNTIME_ERROR"
       ].includes(d.failure_code))details.failure_code=d.failure_code;
       for(const key of ["decision","strategy"]){
         if(typeof d[key]==="string"&&/^(verify|evolve|expand|rollback|balanced|novelty|feasibility)$/.test(d[key]))details[key]=d[key];
       }
       return {run_id:String(row.run_id||""),step_index:Number(row.step_index||0),
         stage:String(row.stage),recorded_at:String(row.recorded_at||""),details};
     });
   return NextResponse.json({configured:true,enabled:true,items},
     {headers:privateHeaders});
 } catch (error) {
   const missing=error instanceof Error && error.message==="LAB_HTTP_404";
   return NextResponse.json({
     configured:true,enabled:false,items:[],
     detail:missing?
       "实时事件表尚不存在：请先在独立 Supabase 实验库执行 SQL 007。":
       "实时事件服务暂时不可用，请检查实验库访问权限。"
   },{headers:privateHeaders});
 }
}
