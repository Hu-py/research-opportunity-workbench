export type Paper = {
  id:string; title:string; abstract:string; doi:string; url:string;
  published:string; venue:string; line_ids:string[];
};
export type Idea = {
  id:string;line_id:string;method:string;title:string;hypothesis:string;
  caveat:string;status:string;score:number;version:number;
  updated_at:string;papers:Paper[];
};
export type ResearchLine = {
  id:string;name:string;problem:string;keywords:string[];
  search_queries:string[];method_queries:string[];
};
export type Profile = {
  research_lines:ResearchLine[];excluded_terms?:string[];goals?:string;
  team?:{name?:string;mission?:string;priorities?:string[]};
  datasets?:{name:string;description?:string;access?:string}[];
  methods?:string[];
};
export type PersonalProfileEvidence = {
  id:string;line_id:string;kind:"publication"|"agent_report"|"project"|"dataset";
  title:string;url:string;note?:string;
};
export type PersonalResearchProfile = {
  research_lines:ResearchLine[];goals:string;methods:string[];
  excluded_terms:string[];evidence:PersonalProfileEvidence[];
};
export type PersonalResearchAssetKind =
  | "publication" | "agent_report" | "experiment_result" | "project" | "dataset" | "note";
export type PersonalResearchAsset = {
  id:string;client_key:string;kind:PersonalResearchAssetKind;title:string;
  summary:string;url:string;source_type:string;source_id:string;
  metadata:Record<string,unknown>;line_ids:string[];status:"active"|"archived";
  created_at:string|null;updated_at:string|null;
};
export type TaskSourceScope = {
  scene:string;groups:{A:string[];B:string[];C:string[]};
  enforced:boolean;scope_version?:number;version?:number;configured?:boolean;
};
export type ResearchSourceLabel = {id:string;name:string;abbreviation:string};
export type TaskEvent = {at:string;step:string;detail:string};
export type Task = {
  id:string;kind:"explore"|"sync"|"weekly";query:string;
  status:"queued"|"running"|"completed"|"failed";events:TaskEvent[];
  result:{mode?:string;answer?:string;sources?:Paper[];usage?:Record<string,number>;papers?:unknown;ideas?:unknown};
  error:string;created_at:string;updated_at:string;
  source_scope?:TaskSourceScope;
};
export type Overview = {papers:number;ideas:number;revisions:number;research_lines:number;cusp_datasets:number;extra_data_assets:number;recent_ideas:Idea[]};

export type TeamMember = {
  id:string;email:string;name:string;role:"admin"|"researcher"|"viewer";
  active:boolean;created_at?:string;
};
export type TeamAudit = {
  id:number;actor_id:string|null;action:string;target:string;note:string;created_at:string;
};
