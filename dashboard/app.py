# 개발자가 Gold 지표를 한 화면에서 확인하는 수동 조회 Streamlit 대시보드다.
# 페이지 재실행만으로 Athena 비용이 발생하지 않도록 버튼을 눌렀을 때만 조회한다.

from __future__ import annotations

import streamlit as st

from athena import AthenaQueryError, run_queries, run_query
from queries import VERSIONS_QUERY, build_dashboard_queries


st.set_page_config(page_title="PANDOK Game Analytics", layout="wide")
st.title("PANDOK Game Analytics")
st.caption("Gold Iceberg · AWS Sydney · manual refresh")

if "versions" not in st.session_state:
    st.session_state.versions = []
if "dashboard_data" not in st.session_state:
    st.session_state.dashboard_data = None

if st.sidebar.button("Load game versions"):
    try:
        rows = run_query(VERSIONS_QUERY)
        st.session_state.versions = [row["game_version"] for row in rows]
    except AthenaQueryError as error:
        st.sidebar.error(str(error))

version_options = ["All versions", *st.session_state.versions]
selected_version = st.sidebar.selectbox("Game version", version_options)

if st.sidebar.button("Refresh dashboard", type="primary"):
    version = None if selected_version == "All versions" else selected_version
    try:
        with st.spinner("Querying Athena Gold tables..."):
            st.session_state.dashboard_data = run_queries(
                build_dashboard_queries(version)
            )
    except AthenaQueryError as error:
        st.error(str(error))

data = st.session_state.dashboard_data
if data is None:
    st.info("Load versions, choose a filter, then press Refresh dashboard.")
    st.stop()

overview = data["run_overview"][0] if data["run_overview"] else {}
columns = st.columns(4)
for column, label, key in zip(
    columns,
    ("Total Runs", "Started", "Ended", "Incomplete"),
    ("total_run_count", "started_run_count", "ended_run_count", "incomplete_run_count"),
    strict=True,
):
    column.metric(label, overview.get(key, "0"))

st.subheader("Run endings and death causes")
st.dataframe(data["run_endings"], width="stretch", hide_index=True)

st.subheader("Run progression")
st.dataframe(data["run_progression"], width="stretch", hide_index=True)

st.subheader("Item performance summary")
st.caption("INSUFFICIENT_SAMPLE means fewer than 30 ended Runs were observed for the item.")
st.dataframe(data["item_performance"], width="stretch", hide_index=True)

st.subheader("Weapon popularity")
st.caption("Selection percentage uses weapon exposures as its denominator.")
st.dataframe(data["weapon_popularity"], width="stretch", hide_index=True)

st.subheader("Starting weapon performance")
st.caption("Kill and survival differences are descriptive, not causal effects.")
st.dataframe(data["weapon_performance"], width="stretch", hide_index=True)

st.subheader("Selected vs not selected option outcomes")
st.caption("Only Runs that were actually offered each option are compared.")
st.dataframe(data["option_outcomes"], width="stretch", hide_index=True)

st.subheader("Data quality")
st.dataframe(data["run_quality"], width="stretch", hide_index=True)
