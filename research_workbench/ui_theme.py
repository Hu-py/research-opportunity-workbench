"""Visual system for the Streamlit research workbench."""
from __future__ import annotations
import html
import streamlit as st

def safe(value):
    return html.escape(str(value or ""), quote=True)

def install_theme():
    st.markdown("""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
      :root { --navy:#14263f; --violet:#6557ce; --sky:#eef3fa; }
      .stApp { background: #f7f9fc; color:#25334b; }
      html, body, [class*="css"], [data-testid="stAppViewContainer"] {
          font-family: "DM Sans","PingFang SC","Microsoft YaHei",sans-serif;
      }
      [data-testid="stMainBlockContainer"] {max-width: 1280px; padding-top: 2rem; padding-bottom: 5rem;}
      [data-testid="stSidebar"] {background: #14263f !important;}
      [data-testid="stSidebar"] * {color:#f0f4ff !important;}
      [data-testid="stSidebar"] [role="radiogroup"] label { padding: 9px 8px; border-radius: 10px; }
      [data-testid="stSidebar"] [role="radiogroup"] label:hover {background:#223b5b;}
      [data-testid="stSidebar"] .stCaption {color:#a5bbd3 !important;}
      h1,h2,h3 { color:#172b47; letter-spacing:-.02em;}
      [data-testid="stMetric"] {background:white;border:1px solid #e4e9f0;border-radius:16px;padding:18px 20px;box-shadow:0 3px 14px rgba(27,47,78,.025)}
      [data-testid="stMetricLabel"] {color:#6b7d94;}
      [data-testid="stMetricValue"] {color:#172b47;font-weight:750;}
      [data-testid="stVerticalBlockBorderWrapper"] {border-color:#e5eaf2 !important;border-radius:16px !important;background:white;box-shadow:0 3px 12px rgba(26,44,73,.018);}
      div.stButton > button[kind="primary"],div.stFormSubmitButton > button[kind="primary"] {
          background:#6557ce;border-color:#6557ce;border-radius:10px;min-height:40px;font-weight:600;
      }
      div.stButton > button {border-radius:10px;}
      [data-testid="stDownloadButton"] button {border-radius:10px;}
      a {color:#5147bb;}
      .hero { border-radius:23px; padding:30px 34px; color:white; background:
          radial-gradient(circle at 88% 15%,rgba(186,179,255,.4) 0,transparent 31%),
          linear-gradient(120deg,#152a4a 0%,#263e71 52%,#6557ce 100%);
          margin-bottom:21px; box-shadow:0 15px 30px rgba(38,51,101,.13);}
      .hero h1{font-size:28px;letter-spacing:-.7px;color:#fff;margin:8px 0 8px;}
      .hero p{color:#e1e6fa;font-size:14px;max-width:680px;margin:0;line-height:1.8;}
      .eyebrow{font-size:11px;letter-spacing:2px;font-weight:700;color:#a9c8ff;}
      .page-kicker{font-size:11px;letter-spacing:1.5px;color:#756aca;font-weight:800;margin:4px 0;}
      .pill{display:inline-block;font-size:11px;padding:5px 10px;border-radius:99px;background:#f0ecff;color:#564bb5;font-weight:600;margin-right:6px}
      .pill-green{background:#e8f7ef;color:#287952;}
      .section-note{color:#718097;font-size:13px;margin-top:-8px;margin-bottom:16px;}
      .micro{color:#8791a3;font-size:11px;}
      .divider-space{height:10px;}
      .paper-title{font-size:15px;font-weight:700;color:#1b2c47;line-height:1.45;margin:0 0 7px;}
      .paper-meta{color:#75859b;font-size:12px;margin-bottom:8px;}
      .note-panel{background:#f4f6ff;border:1px solid #e9e6ff;border-radius:12px;padding:13px 16px;margin:8px 0}
      .note-panel p{margin:0;color:#51607a;font-size:13px;line-height:1.8}
    </style>
    """, unsafe_allow_html=True)

def hero(title, subtitle, eyebrow="RESEARCH INTELLIGENCE"):
    st.markdown(
        '<div class="hero"><div class="eyebrow">'+safe(eyebrow)+'</div><h1>'+
        safe(title)+'</h1><p>'+safe(subtitle)+'</p></div>',
        unsafe_allow_html=True
    )

def section(title, caption=None):
    st.subheader(title)
    if caption:
        st.markdown('<p class="section-note">'+safe(caption)+'</p>',unsafe_allow_html=True)

def tag(name, green=False):
    return '<span class="pill'+(' pill-green' if green else '')+'">'+safe(name)+'</span>'
