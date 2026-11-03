"""Chinese research intelligence dashboard, connected to the persisted MVP backend."""
from __future__ import annotations

import hmac
import json
import os
from datetime import date
from pathlib import Path

import streamlit as st
from sqlalchemy import func, select

from research_workbench.core import (
    Paper, Idea, Evidence, Event, session_factory, get_profile, set_profile,
    ingest, propose, feedback, weekly_report,
)
from research_workbench.ui_theme import install_theme, hero, section, safe, tag

st.set_page_config(
    page_title="科研机会工作台 | Research Intelligence",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)
install_theme()

# Privacy boundary: public cloud deployments must set WORKBENCH_REQUIRE_AUTH=true
# and supply APP_PASSWORD through environment/Streamlit secrets.
def secret(name, fallback=""):
    try:
        return os.getenv(name) or st.secrets.get(name, fallback)
    except (FileNotFoundError, AttributeError, KeyError):
        return os.getenv(name, fallback)

if str(secret("WORKBENCH_REQUIRE_AUTH", "")).lower() in ("1","true","yes"):
    expected=secret("APP_PASSWORD")
    if not expected:
        st.error("工作台已启用访问保护，但尚未配置 APP_PASSWORD。请在部署平台的 Secrets 中设置。")
        st.stop()
    if not st.session_state.get("_authenticated"):
        hero("科研机会工作台","此工作台存储个人科研画像及研究选题。请输入访问密码。","RESTRICTED ACCESS")
        with st.form("login"):
            password=st.text_input("访问密码",type="password")
            if st.form_submit_button("进入工作台",type="primary"):
                if hmac.compare_digest(password,expected):
                    st.session_state["_authenticated"]=True
                    st.rerun()
                else: st.error("密码不正确")
        st.stop()

Session=session_factory()
NAV=[
    ("📊","科研总览"),
    ("📚","论文情报库"),
    ("💡","研究选题池"),
    ("🔄","选题演化"),
    ("🧬","研究者画像"),
    ("📰","每周科研简报"),
    ("⚙️","系统设置"),
]
STATES={
    "candidate":"待评估","watch":"持续关注","shortlist":"重点选题",
    "experiment":"准备实验","rejected":"暂不考虑","archived":"已归档",
}
with st.sidebar:
    st.markdown("## 🔬 Research Atlas")
    st.caption("PERSONAL RESEARCH INTELLIGENCE")
    st.divider()
    page=st.radio("工作台导航",[name for _,name in NAV],format_func=lambda name:next(icon+"  "+name for icon,n in NAV if name==n),label_visibility="collapsed")
    st.divider()
    st.caption("● 研究资料仅存于配置的数据库")
    st.caption("MVP 0.2 · 来源可追溯 · 人工审核")
    if st.session_state.get("_authenticated") and st.button("退出登录"):
        st.session_state["_authenticated"]=False
        st.rerun()

with Session() as db:
    profile=get_profile(db)
    all_lines=(profile or {}).get("research_lines",[])
    line_names={line["id"]:line["name"] for line in all_lines}
    paper_count=db.scalar(select(func.count()).select_from(Paper)) or 0
    idea_count=db.scalar(select(func.count()).select_from(Idea)) or 0
    event_count=db.scalar(select(func.count()).select_from(Event)) or 0

    if page=="科研总览":
        hero("早上好，探索下一个研究机会。","从跨领域论文发现到选题假设、证据积累和实验决策，让每周的科研进展形成长期可追溯的知识资产。")
        c1,c2,c3,c4=st.columns(4)
        c1.metric("已收录论文",paper_count)
        c2.metric("累计研究选题",idea_count)
        c3.metric("选题演化记录",event_count)
        c4.metric("跟踪研究方向",len(all_lines))
        st.write("")
        left,right=st.columns([1.7,1],gap="large")
        with left:
            section("最近的研究机会","按照当前筛选分排序；评分是检索优先级，不等于创新性或发表概率")
            ideas=db.scalars(select(Idea).order_by(Idea.score.desc()).limit(6)).all()
            if not ideas:
                st.info("尚无研究选题。请先在「研究者画像」填写研究方向，再启动一次文献采集。")
            for i in ideas:
                with st.container(border=True):
                    st.markdown("**"+safe(i.title)+"**")
                    st.caption((line_names.get(i.line_id,i.line_id))+" · "+STATES.get(i.status,i.status)+" · v"+str(i.version))
                    st.write(i.hypothesis)
                    st.progress(min(max(int(i.score),0),100),text="初筛分 "+str(round(i.score))+" / 100")
            section("最新收录论文")
            papers=db.scalars(select(Paper).order_by(Paper.published.desc()).limit(5)).all()
            if not papers:st.caption("数据库暂无论文。")
            for p in papers:
                with st.container(border=True):
                    st.markdown("**"+safe(p.title)+"**")
                    st.caption((p.venue or "来源待核验")+" · "+(p.published or "日期未知"))
                    if p.url:st.link_button("查看原文 ↗",p.url)
        with right:
            section("执行研究任务","在当前研究画像上采集论文并更新选题证据")
            with st.container(border=True):
                lookback=st.number_input("检索最近多少天",min_value=1,max_value=365,value=14)
                per_query=st.slider("每个检索词的论文上限",3,50,15)
                if not profile:
                    st.warning("请先创建研究者画像，才能运行检索。")
                if st.button("🔎 更新文献与选题",type="primary",disabled=not bool(profile),use_container_width=True):
                    with st.spinner("正在检索 OpenAlex、去重并分析研究选题…"):
                        try:
                            stats=ingest(db,profile,days=int(lookback),limit=int(per_query))
                            result=propose(db,profile)
                            st.success(f"新增论文 {stats['new_papers']} 篇 · 新选题 {result['new_ideas']} 个 · 更新 {result['revised_ideas']} 个")
                            if stats["failed_queries"]:
                                st.warning(f"{len(stats['failed_queries'])} 个检索词失败，请稍后重试。")
                        except Exception as e:st.error("任务执行失败："+str(e))
            section("研究方向")
            if not all_lines:st.caption("尚未建立研究方向档案。")
            for line in all_lines:
                with st.container(border=True):
                    st.markdown("**"+line["name"]+"**")
                    st.caption(line["problem"])
                    st.markdown(tag("领域检索")+" "+tag("方法迁移"),unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("**如何开始？**")
                st.write("① 完善研究者画像")
                st.write("② 运行跨领域文献检索")
                st.write("③ 在选题池审核与反馈")
                st.write("④ 在每周简报中回看新证据")

    elif page=="论文情报库":
        hero("跨领域论文情报库","统一检索规划领域与计算机方法论文，保留来源、摘要及对应研究方向。","LITERATURE DISCOVERY")
        a,b=st.columns([3,1])
        search=a.text_input("搜索论文",placeholder="关键词、标题、摘要或期刊名称")
        selected=b.selectbox("研究方向",["所有方向"]+list(line_names.values()))
        rows=db.scalars(select(Paper).order_by(Paper.published.desc()).limit(2000)).all()
        matched=[]
        for p in rows:
            text=(p.title+" "+(p.abstract or "")+" "+(p.venue or "")).lower()
            ids=json.loads(p.line_ids or "[]")
            if search and search.lower() not in text:continue
            if selected!="所有方向" and selected not in [line_names.get(x,x) for x in ids]:continue
            matched.append(p)
        st.caption(f"符合条件的论文：{len(matched)} 篇（最多展示 200 篇）")
        if not matched:st.info("尚未收录匹配的论文。可以返回科研总览运行检索。")
        for p in matched[:200]:
            with st.container(border=True):
                st.markdown('<div class="paper-title">'+safe(p.title)+'</div>',unsafe_allow_html=True)
                st.markdown('<div class="paper-meta">'+safe(p.venue or "会议/期刊待核验")+"  ·  "+safe(p.published or "无日期")+'</div>',unsafe_allow_html=True)
                if p.abstract:
                    with st.expander("展开摘要"):
                        st.write(p.abstract)
                ids=json.loads(p.line_ids or "[]")
                st.markdown(" ".join(tag(line_names.get(x,x)) for x in ids),unsafe_allow_html=True)
                if p.url:st.link_button("查看论文原文 ↗",p.url)

    elif page=="研究选题池":
        hero("滚动研究选题池","每个选题都关联原始论文证据。新增文献只扩充或修订既有选题，不丢失历史反馈。","OPPORTUNITY PIPELINE")
        filter_col,sort_col=st.columns(2)
        status=filter_col.selectbox("筛选选题状态",["全部状态"]+list(STATES.values()))
        sort=sort_col.selectbox("排序方式",["优先级由高到低","最近更新"])
        order=Idea.score.desc() if sort=="优先级由高到低" else Idea.updated_at.desc()
        ideas=db.scalars(select(Idea).order_by(order).limit(300)).all()
        ideas=[i for i in ideas if status=="全部状态" or STATES.get(i.status)==status]
        st.caption(f"当前 {len(ideas)} 个选题")
        if not ideas:st.info("暂无匹配选题。请先在总览中更新文献与选题。")
        for i in ideas:
            with st.container(border=True):
                c1,c2=st.columns([4,1])
                c1.markdown("### "+safe(i.title))
                c1.caption(line_names.get(i.line_id,i.line_id)+" · "+i.method)
                c2.metric("初筛分",str(round(i.score))+"/100")
                st.markdown(tag(STATES.get(i.status,i.status),green=i.status in ("shortlist","experiment"))+" "+tag("V"+str(i.version)),unsafe_allow_html=True)
                st.write("**待验证研究假设：** "+i.hypothesis)
                with st.expander("支撑文献与风险说明"):
                    st.warning(i.caveat)
                    ids=db.scalars(select(Evidence.paper_id).where(Evidence.idea_id==i.id)).all()
                    for paper_id in ids:
                        p=db.get(Paper,paper_id)
                        if p:st.markdown("- ["+p.title+"]("+p.url+")")
                with st.form("decide_"+i.id,clear_on_submit=True):
                    a,b=st.columns([1,3])
                    choice=a.selectbox("更新状态",list(STATES.keys()),index=list(STATES.keys()).index(i.status),format_func=lambda v:STATES[v])
                    note=b.text_input("给这个选题的反馈",placeholder="例如：有相关数据，可先做标签稀疏性实验")
                    if st.form_submit_button("保存反馈"):
                        feedback(db,i.id,choice,note)
                        st.success("反馈已写入演化历史")
                        st.rerun()

    elif page=="选题演化":
        hero("选题演化与证据时间线","追踪每个研究假设从首次发现到文献补充、人工决策的完整过程。","IDEA EVOLUTION")
        ideas=db.scalars(select(Idea).order_by(Idea.updated_at.desc())).all()
        if not ideas:st.info("尚无历史记录；生成选题后会在这里自动积累。")
        else:
            options={i.id:i.title for i in ideas}
            target=st.selectbox("选择一个选题",list(options),format_func=lambda key:options[key])
            i=db.get(Idea,target)
            st.subheader(i.title)
            st.caption("当前状态："+STATES.get(i.status,i.status)+"  ·  当前版本：V"+str(i.version))
            events=db.scalars(select(Event).where(Event.idea_id==target).order_by(Event.version.desc())).all()
            for e in events:
                with st.container(border=True):
                    st.markdown("**V"+str(e.version)+" · "+({"created":"首次提出","evidence_added":"新增文献证据","feedback":"研究者反馈"}.get(e.action,e.action))+"**")
                    st.caption(str(e.created_at)[:19])
                    try:
                        details=json.loads(e.detail or "{}")
                        if details.get("new_paper_ids"):
                            st.write("新增证据：")
                            for pid in details["new_paper_ids"]:
                                p=db.get(Paper,pid)
                                if p:st.markdown("- ["+p.title+"]("+p.url+")")
                        if "status" in details:st.write("状态："+STATES.get(details["status"],details["status"]))
                        if details.get("note"):st.info(details["note"])
                    except (ValueError,TypeError):st.caption(e.detail)

    elif page=="研究者画像":
        hero("研究者画像与研究能力边界","用研究问题、可用数据、技术基础和研究偏好推动个性化推荐；画像保存在数据库，不自动公开到 GitHub。","RESEARCHER PROFILE")
        if not profile:st.info("这是首次使用。可以先用示例研究方向进行测试，再替换为你自己的真实研究画像。")
        source=profile or json.loads((Path(__file__).parent/"examples/profile.example.json").read_text(encoding="utf-8"))
        st.subheader("研究方向档案")
        for line in source["research_lines"]:
            with st.container(border=True):
                st.markdown("**"+line["name"]+"**")
                st.write(line["problem"])
                st.caption("方法检索："+", ".join(line["method_queries"]))
        st.divider()
        st.subheader("编辑研究画像")
        st.caption("可先上传 PDF/Word 的文字整理成果，后续再引入自动解析与知识抽取。当前版本使用结构化 JSON，可直接保存、备份和导入。")
        with st.form("researcher_profile"):
            edited=st.text_area("Research Profile JSON",json.dumps(source,ensure_ascii=False,indent=2),height=380)
            submitted=st.form_submit_button("验证并保存研究画像",type="primary")
            if submitted:
                try:
                    set_profile(db,json.loads(edited))
                    st.success("保存成功")
                    st.rerun()
                except (ValueError,TypeError,json.JSONDecodeError) as ex:st.error("画像格式错误："+str(ex))
        st.download_button("导出当前研究画像 JSON",json.dumps(source,ensure_ascii=False,indent=2),file_name="research-profile.json",mime="application/json")

    elif page=="每周科研简报":
        hero("每周科研机会简报","本周新论文、持续更新的选题及其依据，集中呈现为可导出的研究报告。","WEEKLY RESEARCH BRIEF")
        if not profile:st.info("建立研究画像后，才可生成个性化周报。")
        else:
            md=weekly_report(db,profile,days=7)
            a,b=st.columns([3,1])
            a.markdown("**研究简报 · "+date.today().isoformat()+"**")
            b.download_button("⬇ 导出 Markdown",md,file_name="research-brief-"+date.today().isoformat()+".md",mime="text/markdown",use_container_width=True)
            with st.container(border=True):st.markdown(md)
            st.caption("提示：周报不代表实时检索结果。请在总览先运行论文更新，再生成本周简报。")

    else:
        hero("系统设置与数据安全","控制数据库、自动化推送与云端部署的前置配置。","WORKBENCH SETTINGS")
        st.subheader("运行状态")
        db_url=os.getenv("DATABASE_URL","")
        st.write("数据库：", "外部持久化数据库已配置" if db_url else "本地 SQLite（演示/本地使用）")
        st.write("登录保护：", "已启用" if str(secret("WORKBENCH_REQUIRE_AUTH","")).lower() in ("1","true","yes") else "未启用")
        st.write("科研方向：",len(all_lines),"个")
        st.subheader("需要注意")
        st.warning("不要在公开工作台中保存未发表论文、个人研究计划或隐私数据。云部署前必须启用密码保护并配置持久化数据库。")
        st.markdown("**自动化设置**：每周任务由 GitHub Actions 运行，需配置 DATABASE_URL，并设置 ENABLE_WEEKLY=true。")
        st.markdown("**数据来源**：当前以 OpenAlex 为主，跨领域选题由规则识别生成；尚未包含全面的论文精读、学术创新性验证。")
        st.markdown("[查看 GitHub 仓库](https://github.com/Hu-py/research-opportunity-workbench)")
