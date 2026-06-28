from __future__ import annotations

import streamlit as st
import plotly.express as px
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from ingest_world_cup import Settings
from transforms import load_matches, group_standings, team_stats, match_log

st.set_page_config(page_title="World Cup 2026", layout="wide")
st.title("World Cup 2026 — Live Tracker")

engine = create_engine(Settings().build_dsn())

TAB_GROUPS, TAB_TEAMS, TAB_MATCHES, TAB_KNOCKOUT = st.tabs(
    ["Group Standings", "Team Rankings", "Match Log", "Knockout Bracket"]
)


@st.cache_data(ttl=300)
def get_data():
    df = load_matches(engine)
    return df, group_standings(df), team_stats(df)


df, standings, teams = get_data()

# ────────────────────────────────────────────── Group Standings ──────────────────

with TAB_GROUPS:
    for group in sorted(standings["group"].unique()):
        with st.expander(f"**{group.replace('_', ' ')}**", expanded=True):
            tbl = standings[standings["group"] == group].drop(columns=["group"]).copy()
            tbl["pos"] = tbl["pos"].astype(str) + "."
            tbl = tbl.rename(columns={
                "pos": "#", "team": "Team", "pj": "PJ", "w": "W", "d": "D",
                "l": "L", "gf": "GF", "ga": "GA", "gd": "GD", "pts": "Pts",
            })
            st.dataframe(
                tbl.set_index("#"),
                column_config={
                    "GD": st.column_config.NumberColumn(format="%+d"),
                },
                hide_index=False,
                width="stretch",
            )

# ────────────────────────────────────────────── Team Rankings ───────────────────

with TAB_TEAMS:
    metric = st.selectbox("Metric", ["gd", "gf", "ga", "avg_gf", "avg_ga"],
                          format_func=lambda x: {
                              "gd": "Goal Difference", "gf": "Goals Scored",
                              "ga": "Goals Conceded", "avg_gf": "Avg Goals Scored",
                              "avg_ga": "Avg Goals Conceded",
                          }.get(x, x))
    top_n = st.slider("Show top N", 5, 48, 15)
    top = teams.nlargest(top_n, metric)
    fig = px.bar(top, x="team", y=metric, color=metric,
                 color_continuous_scale="Blues", text=metric)
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_title="", yaxis_title="",
                      height=500, margin=dict(t=10))
    st.plotly_chart(fig, width="stretch")

# ────────────────────────────────────────────── Match Log ────────────────────────

with TAB_MATCHES:
    round_opts = ["All"] + sorted(df["round"].unique().tolist())
    rnd = st.selectbox("Round", round_opts)
    team_opts = ["All"] + sorted(
        set(df["home_team"].unique()) | set(df["away_team"].unique())
    )
    tm = st.selectbox("Team", team_opts)

    filtered = match_log(df)
    if rnd != "All":
        filtered = filtered[filtered["round"] == rnd]
    if tm != "All":
        filtered = filtered[
            (filtered["home_team"] == tm) | (filtered["away_team"] == tm)
        ]

    st.dataframe(
        filtered.rename(columns={
            "match_utc": "Date (UTC)", "round": "Round",
            "group_name": "Group", "home_team": "Home",
            "score": "Score", "away_team": "Away",
        }),
        column_config={"Date (UTC)": st.column_config.DatetimeColumn(format="DD MMM, HH:mm")},
        hide_index=True,
        width="stretch",
    )

# ────────────────────────────────────────────── Knockout Bracket ────────────────

with TAB_KNOCKOUT:
    kd = df[df["round"] != "GROUP_STAGE"]
    if kd.empty:
        st.info("Knockout stage starts today (28 Jun 2026). Data will appear here as matches finish.")
    else:
        st.dataframe(kd)
