// Reference entries transcribed from the approved UI V0.2 design.
// These are NOT production source-list records and must always be labeled
// as design recommendations, not enabled ingestion sources.
export const moduleLabels: Record<string,string> = {
  DISCOVERY: "A/B/C 文献发现与核验",
  PAPER_KNOWLEDGE: "单篇知识与证据抽取",
  SIGNAL_L1: "跨论文研究信号综合",
  DEEP_READ_L2: "代表论文深读",
  IDEA_L3: "方法迁移与研究机会",
  TEAM_FIT: "团队能力与研究匹配",
  DELIVERY: "周报与定向任务交付",
  PLATFORM: "平台、权限与运行",
};
export const moduleScopes:Record<string,string> = {
  DISCOVERY:"SC01 · SC03",PAPER_KNOWLEDGE:"共用核心",
  SIGNAL_L1:"SC01 · SC02",DEEP_READ_L2:"SC03",
  IDEA_L3:"SC03（可选）",TEAM_FIT:"共用核心",
  DELIVERY:"SC01 · SC02 · SC03",PLATFORM:"基础设施",
};
export const designSources = [
  {id:"SCS-REF-01",name:"Cities",short:"Cities",group:"A",kind:"期刊",priority:"核心",channel:"OpenAlex / 官网",status:"待核验",url:"https://www.sciencedirect.com/journal/cities",reason:"城市规划应用、治理和空间研究"},
  {id:"SCS-REF-02",name:"Sustainable Cities and Society",short:"SCS",group:"A",kind:"期刊",priority:"核心",channel:"OpenAlex / 官网",status:"已知分页问题",url:"https://www.sciencedirect.com/journal/sustainable-cities-and-society",reason:"城市可持续发展与实际应用"},
  {id:"SCS-REF-03",name:"Land Use Policy",short:"LUP",group:"A",kind:"期刊",priority:"重点",channel:"OpenAlex",status:"待核验",url:"https://www.sciencedirect.com/journal/land-use-policy",reason:"土地利用、空间政策与规划实践"},
  {id:"SCS-REF-04",name:"Environment and Planning B: Urban Analytics and City Science",short:"EPB",group:"B",kind:"期刊",priority:"核心",channel:"OpenAlex / 官网",status:"哨兵 3/3",url:"https://journals.sagepub.com/home/epba",reason:"城市科学新问题、新视角与新测量"},
  {id:"SCS-REF-05",name:"Computers, Environment and Urban Systems",short:"CEUS",group:"B",kind:"期刊",priority:"核心",channel:"OpenAlex / 官网",status:"待核验",url:"https://www.sciencedirect.com/journal/computers-environment-and-urban-systems",reason:"城市系统的计算方法与问题重构"},
  {id:"SCS-REF-06",name:"Journal of Machine Learning Research",short:"JMLR",group:"C",kind:"期刊",priority:"核心",channel:"官网 / OpenAlex 补查",status:"正式版本归属待核对",url:"https://www.jmlr.org/papers/v27/",reason:"可迁移机器学习技术与公开实现"},
  {id:"SCS-REF-07",name:"NeurIPS",short:"NeurIPS",group:"C",kind:"会议",priority:"重点",channel:"官方论文集 / 索引",status:"待核验",url:"https://neurips.cc/",reason:"前沿机器学习技术"},
] as const;
export const referenceDocuments = [
  {id:"REF-DOC-01",title:"Research Atlas 产品目标与范围",category:"product",module_id:"PLATFORM",url:"https://chatgpt.com/space/page_c8636ac18edc8191aeee11b38130b3ef",source:"ChatGPT Page",revision:"讨论稿"},
  {id:"REF-DOC-02",title:"Research Atlas 三类核心使用场景与共用科研任务设计 V0.2",category:"product",module_id:"DELIVERY",url:"https://chatgpt.com/space/page_57ecd890598881918c1694f4bb9cc45a",source:"ChatGPT Page",revision:"V0.2"},
  {id:"REF-DOC-03",title:"Research Atlas AI 工作流与能力架构设计 V0.1",category:"architecture",module_id:"DISCOVERY",url:"https://chatgpt.com/space/page_4f5d2daf5684819181b1756930835fde",source:"ChatGPT Page",revision:"持续修订"},
  {id:"REF-DOC-04",title:"Development Studio 研发与配置治理平台设计 V0.3",category:"architecture",module_id:"PLATFORM",url:"https://chatgpt.com/space/page_79b08ee99e9081918e3363df6ee1e9a3",source:"ChatGPT Page",revision:"V0.3"},
  {id:"REF-DOC-05",title:"OpenAlex × 期刊官网真实采集对照报告",category:"evaluation",module_id:"DISCOVERY",url:"https://github.com/Hu-py/research-opportunity-workbench/blob/feature/atlas-three-source-ai-workflow-v01/experiments/atlas_pilot_2026_11_14/REPORT.md",source:"GitHub",revision:"2026-11-14"},
] as const;
export const workflows = [
  {id:"SC01",name:"团队科研周报",status:"设计与试验",schedule:"每周",scope:"共享科研发现与每周学习",steps:["A/B/C 来源采集","证据规范化","L1 多论文综合","科研审核与周报"]},
  {id:"SC02",name:"个人科研周报",status:"产品规划",schedule:"每周 / 按需",scope:"授权的个人研究画像与学习计划",steps:["共享候选文献","个人研究画像","定向综合","个人科研简报"]},
  {id:"SC03",name:"定向科研任务",status:"设计与试验",schedule:"按需",scope:"指定问题、方法与证据核验",steps:["任务与范围设定","证据检索","L1 / L2 深读","可选 L3 研究行动"]},
] as const;
export const groupTitles:Record<string,string> = {
  A:"A · 规划应用",B:"B · 城市科学",C:"C · 计算方法",
  planning_application:"A · 规划应用",
  urban_science:"B · 城市科学",
  computational_methods:"C · 计算方法",
};
export const categoryTitles:Record<string,string> = {
  product:"产品与需求",architecture:"技术与架构",data:"数据与接口",
  evaluation:"实验与评测",decision:"技术决策",operations:"运行与交接",
};
