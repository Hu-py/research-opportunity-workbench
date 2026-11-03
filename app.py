"""Local Streamlit workbench; do not publicly deploy without authentication."""
import json
from pathlib import Path
import streamlit as st
from sqlalchemy import func, select
from research_workbench.core import (
    Paper,Idea,Evidence,Event,session_factory,get_profile,set_profile,
    ingest,propose,feedback,weekly_report
)

st.set_page_config(page_title="Research Opportunity Workbench",page_icon="🔬",layout="wide")
st.title("Research Opportunity Workbench")
st.caption("Evidence-linked literature discovery · interdisciplinary method transfer · rolling ideas")
Factory=session_factory()
with Factory() as db:
    profile=get_profile(db)
    overview,papers_tab,ideas_tab,profile_tab,brief_tab=st.tabs(
        ["Overview","Papers","Ideas","Research profile","Weekly brief"])
    with overview:
        a,b,c=st.columns(3)
        a.metric("Papers",db.scalar(select(func.count()).select_from(Paper)) or 0)
        b.metric("Ideas",db.scalar(select(func.count()).select_from(Idea)) or 0)
        c.metric("Versions",db.scalar(select(func.count()).select_from(Event)) or 0)
        if profile:
            days=st.number_input("Look-back days",1,365,14)
            limit=st.slider("Results per query",3,50,15)
            if st.button("Update literature and research ideas",type="primary"):
                with st.spinner("Searching and matching papers..."):
                    stats=ingest(db,profile,days=int(days),limit=int(limit))
                    changes=propose(db,profile)
                st.success(str(stats)+" | "+str(changes))
        else:st.info("Create your profile to begin.")
        st.warning("Screening scores are heuristics. Novelty and experiment feasibility still require verification.")
    with papers_tab:
        filter_text=st.text_input("Search indexed titles and abstracts")
        rows=db.scalars(select(Paper).order_by(Paper.published.desc()).limit(1000)).all()
        matched=[p for p in rows if filter_text.lower() in (p.title+" "+p.abstract+" "+p.venue).lower()]
        for p in matched[:150]:
            with st.expander(p.title+" · "+p.published):
                st.write(p.venue or "Unverified venue")
                st.write(p.abstract or "No abstract indexed")
                st.link_button("Open original",p.url)
    with ideas_tab:
        status_filter=st.selectbox("Filter status",["all","candidate","watch","shortlist","experiment","rejected","archived"])
        for idea in db.scalars(select(Idea).order_by(Idea.score.desc()).limit(200)):
            if status_filter not in ("all",idea.status):continue
            with st.expander(f"{idea.title} · v{idea.version} · {idea.status}"):
                st.write(idea.hypothesis)
                st.caption(idea.caveat)
                st.write(f"Screening priority: {idea.score:.0f}/100")
                ids=db.scalars(select(Evidence.paper_id).where(Evidence.idea_id==idea.id)).all()
                for pid in ids:
                    paper=db.get(Paper,pid)
                    if paper:st.markdown(f"- [{paper.title}]({paper.url})")
                history=db.scalars(select(Event).where(Event.idea_id==idea.id).order_by(Event.version.desc())).all()
                st.caption("History: "+" · ".join(f"v{h.version} {h.action}" for h in history[:10]))
                with st.form("feedback-"+idea.id):
                    decision=st.selectbox("Status",["watch","shortlist","experiment","rejected","archived","candidate"],key="decision-"+idea.id)
                    note=st.text_input("Reason / research notes",key="note-"+idea.id)
                    if st.form_submit_button("Save feedback"):
                        feedback(db,idea.id,decision,note);st.rerun()
    with profile_tab:
        if profile is None:
            profile=json.loads((Path(__file__).parent/"examples/profile.example.json").read_text(encoding="utf-8"))
        data=st.text_area("Private research profile JSON",json.dumps(profile,ensure_ascii=False,indent=2),height=350)
        if st.button("Validate and save"):
            try:set_profile(db,json.loads(data));st.success("Saved");st.rerun()
            except ValueError as ex:st.error(str(ex))
    with brief_tab:
        if profile:
            report=weekly_report(db,profile)
            st.markdown(report)
            st.download_button("Export Markdown",report,file_name="research-brief.md")
        else:st.info("Create a profile first.")
