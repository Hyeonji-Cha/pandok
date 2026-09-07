"""PANDOK Gold 지표를 보여주는 발표용 수동 조회 대시보드."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from athena import AthenaQueryError, run_queries, run_query
from presentation import localize_rows
from queries import VERSIONS_QUERY, build_dashboard_queries

st.set_page_config(page_title="판독 게임 분석", page_icon="🐺", layout="wide")
st.markdown("""
<style>
:root{--ink:#17233c;--muted:#667085;--green:#27ae84}
.stApp{background:#f5f7fa}[data-testid="stSidebar"]{background:#101828}
[data-testid="stSidebar"] *{color:#f8fafc}[data-testid="stSidebar"] .stButton button{border:0;border-radius:10px;font-weight:700}
.hero{padding:.3rem 0 1rem}.hero h1{color:var(--ink);font-size:2.1rem;margin:0;letter-spacing:-.04em}
.hero .en{color:var(--green);font-size:.8rem;font-weight:800;letter-spacing:.13em;margin-top:.3rem}.hero p{color:var(--muted);margin:.35rem 0 0}
[data-testid="stMetric"]{background:white;border:1px solid #eaecf0;border-radius:14px;padding:1rem;box-shadow:0 4px 18px rgba(16,24,40,.04)}
[data-testid="stMetricValue"]{color:var(--ink);font-weight:750}.section{color:var(--ink);font-size:1.22rem;font-weight:800;margin:1rem 0 .05rem}
.section-en{color:var(--muted);font-size:.78rem;margin-bottom:.7rem}div[data-testid="stDataFrame"]{border:1px solid #eaecf0;border-radius:12px;overflow:hidden}
.cost{padding:.7rem;border:1px solid #344054;border-radius:10px;color:#d0d5dd;font-size:.8rem}#MainMenu,footer{visibility:hidden}
</style>""", unsafe_allow_html=True)

COLORS = ["#27AE84", "#4F7CFF", "#F4B740", "#E56767", "#8B72D8", "#5DB7C4"]

def number(value, default=0.0):
    try: return float(value) if value not in (None, "") else default
    except (TypeError, ValueError): return default

def frame(rows, numeric=()):
    result = pd.DataFrame(rows)
    for column in numeric:
        if column in result: result[column] = pd.to_numeric(result[column], errors="coerce")
    return result

def section(ko, en):
    st.markdown(f'<div class="section">{ko}</div><div class="section-en">{en}</div>', unsafe_allow_html=True)

def styled(figure, height=350):
    figure.update_layout(height=height, margin=dict(l=12,r=12,t=25,b=12), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#344054"), legend_title_text="")
    figure.update_xaxes(showgrid=False, title=None); figure.update_yaxes(gridcolor="#EAECF0", title=None)
    return figure

for key, value in (("versions", []), ("dashboard_data", None)):
    if key not in st.session_state: st.session_state[key] = value

with st.sidebar:
    st.markdown("## 🐺 PANDOK"); st.caption("GAME ANALYTICS CONSOLE"); st.divider()
    if st.button("버전 목록 불러오기", use_container_width=True):
        try: st.session_state.versions = [r["game_version"] for r in run_query(VERSIONS_QUERY)]
        except AthenaQueryError as error: st.error(str(error))
    selected = st.selectbox("게임 버전 · Game Version", ["전체 버전", *st.session_state.versions])
    refresh = st.button("Gold 데이터 새로고침", type="primary", use_container_width=True)
    st.divider(); st.markdown('<div class="cost">자동 조회 없음<br>Athena는 버튼을 누를 때만 실행됩니다.</div>', unsafe_allow_html=True)

if refresh:
    try:
        with st.spinner("Athena Gold 지표를 불러오는 중입니다..."):
            st.session_state.dashboard_data = run_queries(build_dashboard_queries(None if selected == "전체 버전" else selected))
    except AthenaQueryError as error: st.error(str(error))

st.markdown('<div class="hero"><h1>판독 게임 분석</h1><div class="en">PANDOK GAME ANALYTICS</div><p>플레이 흐름, 무기 밸런스, 아이템 선택 효과와 데이터 품질을 한눈에 확인합니다.</p></div>', unsafe_allow_html=True)
data = st.session_state.dashboard_data
if data is None:
    st.info("왼쪽에서 버전을 선택하고 ‘Gold 데이터 새로고침’을 눌러 분석을 시작하세요."); st.stop()

overview = data["run_overview"][0] if data["run_overview"] else {}
total, started, ended, incomplete = (int(number(overview.get(k))) for k in ("total_run_count","started_run_count","ended_run_count","incomplete_run_count"))
cards = st.columns(5)
cards[0].metric("전체 Run · Total", f"{total:,}"); cards[1].metric("시작 Run · Started", f"{started:,}")
cards[2].metric("종료 Run · Ended", f"{ended:,}", f"{ended/total:.0%}" if total else None)
cards[3].metric("미완료 · Incomplete", f"{incomplete:,}", f"{incomplete/total:.0%}" if total else None, delta_color="inverse")
cards[4].metric("평균 생존 · Avg Survival", f"{number(overview.get('average_run_seconds'))/60:.1f}분")

overview_tab, weapon_tab, item_tab, quality_tab = st.tabs(["게임 현황 · Overview","무기 밸런스 · Weapons","아이템과 옵션 · Items","데이터 품질 · Quality"])
with overview_tab:
    left, right = st.columns([1.35,1], gap="large")
    with left:
        section("Run 진행률", "Run Progression")
        df = frame(data["run_progression"], ("elapsed_minutes","reach_percentage"))
        if not df.empty:
            fig = px.area(df, x="elapsed_minutes", y="reach_percentage", color="game_version", markers=True, color_discrete_sequence=COLORS)
            st.plotly_chart(styled(fig), use_container_width=True)
    with right:
        section("사망 원인 분포", "Death Cause Distribution")
        df = frame(data["run_endings"], ("run_count",)); deaths = df[df["end_reason"] == "player_death"].copy() if not df.empty else df
        if not deaths.empty:
            deaths["사망 원인"] = deaths["death_cause"].map({"enemy_damage":"적 공격","fall":"추락","environmental_hazard":"환경 피해","unknown":"분류 불가","not_collected_legacy":"미수집(이전 계약)"}).fillna(deaths["death_cause"])
            fig = px.pie(deaths, names="사망 원인", values="run_count", hole=.62, color_discrete_sequence=COLORS)
            fig.update_traces(textinfo="percent+label", hovertemplate="%{label}<br>Run %{value}<extra></extra>")
            st.plotly_chart(styled(fig), use_container_width=True)
    section("종료 유형 상세", "Run Ending Details")
    st.dataframe(pd.DataFrame(localize_rows(data["run_endings"])), use_container_width=True, hide_index=True)

with weapon_tab:
    pop = frame(data["weapon_popularity"], ("first_selected_run_count",))
    perf = frame(data["weapon_performance"], ("average_total_kills","average_run_seconds","outcome_observed_run_count","kills_per_minute"))
    left, right = st.columns(2, gap="large")
    with left:
        section("가장 먼저 선택한 무기", "First Weapon Selection")
        if not pop.empty:
            fig = px.bar(pop.sort_values("first_selected_run_count"), x="first_selected_run_count", y="display_name", orientation="h", color="display_name", text_auto=True, color_discrete_sequence=COLORS); fig.update_layout(showlegend=False)
            st.plotly_chart(styled(fig), use_container_width=True)
    with right:
        section("시작 무기별 킬과 생존", "Kills and Survival by Starting Weapon")
        if not perf.empty:
            fig = px.scatter(perf, x="average_run_seconds", y="average_total_kills", size="outcome_observed_run_count", color="display_name", text="display_name", hover_data=["kills_per_minute"], color_discrete_sequence=COLORS); fig.update_traces(textposition="top center")
            st.plotly_chart(styled(fig), use_container_width=True)
    section("무기 성과 상세", "Weapon Performance Details")
    st.dataframe(pd.DataFrame(localize_rows(data["weapon_performance"])), use_container_width=True, hide_index=True)

with item_tab:
    outcomes = frame(data["option_outcomes"], ("average_kill_difference","average_run_seconds_difference","offered_run_count"))
    section("옵션 선택과 결과의 연관성", "Option Selection and Observed Outcomes")
    if not outcomes.empty:
        fig = px.scatter(outcomes, x="average_run_seconds_difference", y="average_kill_difference", size="offered_run_count", color="item_category", hover_name="display_name", color_discrete_sequence=COLORS)
        fig.add_hline(y=0,line_dash="dot",line_color="#98A2B3"); fig.add_vline(x=0,line_dash="dot",line_color="#98A2B3")
        st.plotly_chart(styled(fig, 430), use_container_width=True)
    st.caption("점의 크기는 옵션이 제시된 Run 수입니다. 관찰적 비교이며 인과효과를 의미하지 않습니다.")
    left, right = st.columns(2, gap="large")
    with left: section("아이템 성과", "Item Performance"); st.dataframe(pd.DataFrame(localize_rows(data["item_performance"])), use_container_width=True, hide_index=True)
    with right: section("선택·비선택 비교", "Selected vs Not Selected"); st.dataframe(pd.DataFrame(localize_rows(data["option_outcomes"])), use_container_width=True, hide_index=True)

with quality_tab:
    quality = frame(data["run_quality"], ("input_event_count","exact_retry_count","conflicting_duplicate_count"))
    section("파이프라인 품질 상태", "Pipeline Data Quality")
    if not quality.empty:
        q1,q2,q3 = st.columns(3); conflicts = quality["conflicting_duplicate_count"].sum()
        q1.metric("입력 이벤트 · Input Events", f"{quality['input_event_count'].sum():,.0f}"); q2.metric("동일 재전송 · Exact Retries", f"{quality['exact_retry_count'].sum():,.0f}"); q3.metric("충돌 중복 · Conflicts", f"{conflicts:,.0f}", "확인 필요" if conflicts else "정상", delta_color="inverse")
    st.dataframe(pd.DataFrame(localize_rows(data["run_quality"])), use_container_width=True, hide_index=True)
    st.caption("Gold 집계 전 이벤트 중복 제거와 Run 복원 상태를 확인하는 운영용 화면입니다.")
