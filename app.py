from __future__ import annotations

import pandas as pd
import streamlit as st
import plotly.express as px
from sqlalchemy import create_engine

from ingest_world_cup import Settings
from transforms import load_matches, group_standings, team_stats, match_log, knockout_bracket

st.set_page_config(page_title="World Cup 2026", layout="wide")

# ── Football-themed CSS ──────────────────────────────────────────────────────

st.markdown("""
<style>
    .stApp { background: linear-gradient(180deg, #0a1f0a 0%, #1a3a1a 100%); }
    h1, h2, h3, h4, h5, h6,
    .stMarkdown, .stDataFrame, .stSelectbox label, .stSlider label,
    .stTabs [data-baseweb="tab-list"] button,
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        color: #f0f0f0 !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255,255,255,0.05);
        border-radius: 8px;
        padding: 4px;
        gap: 2px;
    }
    .stTabs [data-baseweb="tab-list"] button {
        border-radius: 6px !important;
        background: transparent !important;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        background: #2d8a2d !important;
        color: white !important;
    }
    .stDataFrame [data-testid="StyledDataFrameDataCell"] {
        color: #e0e0e0 !important;
    }
    .stDataFrame thead tr th {
        background: #1a4a1a !important;
        color: #c8f0c8 !important;
        font-weight: 600;
    }
    .stDataFrame tbody tr:nth-child(even) td {
        background: rgba(255,255,255,0.03);
    }
    .stDataFrame tbody tr:nth-child(odd) td {
        background: rgba(0,0,0,0.2);
    }
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-played { background: #2d8a2d; color: white; }
    .badge-live   { background: #e6b800; color: #1a1a1a; }
    .badge-scheduled { background: #555; color: #ccc; }
    .bracket-card {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
    }
    .bracket-card .teams { font-size: 1rem; font-weight: 500; }
    .bracket-card .score { font-size: 1.2rem; font-weight: 700; color: #ffd700; margin: 0 12px; }
    .bracket-card .date  { font-size: 0.8rem; color: #aaa; }
</style>
""", unsafe_allow_html=True)

st.markdown("# World Cup 2026 — Live Tracker")
st.markdown("*Tabla de posiciones · Estadísticas · Eliminatorias*")

with st.sidebar:
    st.markdown("**Preferencias**")
    tz = st.selectbox("Horario", ["UTC", "España (CEST)"], index=1)
    show_es = tz == "España (CEST)"

engine = create_engine(Settings().build_dsn())

TAB_GROUPS, TAB_TEAMS, TAB_MATCHES, TAB_KNOCKOUT = st.tabs([
    "Tabla de Posiciones",
    "Estadísticas",
    "Partidos",
    "Eliminatorias",
])


@st.cache_data(ttl=300)
def get_data():
    df = load_matches(engine)
    return df, group_standings(df), team_stats(df), knockout_bracket(df)


df, standings, teams, bracket = get_data()

# ────────────────────────────────────────────── TABLA DE POSICIONES ──────────

with TAB_GROUPS:
    st.markdown(
        '<p style="color:#aaa;font-size:0.85rem;">'
        "Leyenda: PJ=Partidos Jugados · PG=Ganados · PE=Empatados · "
        "PP=Perdidos · GF=Goles a Favor · GC=Goles en Contra · "
        "DG=Diferencia de Gol · Pts=Puntos</p>",
        unsafe_allow_html=True,
    )

    for group in sorted(standings["group"].unique()):
        label = group.replace("_", " ").title()
        with st.expander(f"**{label}**", expanded=True):
            tbl = standings[standings["group"] == group].drop(columns=["group"]).copy()
            tbl["pos"] = tbl["pos"].astype(str) + "."
            tbl = tbl.rename(columns={
                "pos": "#", "team": "Equipo", "pj": "PJ", "w": "PG",
                "d": "PE", "l": "PP", "gf": "GF", "ga": "GC",
                "gd": "DG", "pts": "Pts",
            })
            st.dataframe(
                tbl.set_index("#"),
                column_config={
                    "DG": st.column_config.NumberColumn(format="%+d"),
                },
                hide_index=False,
                width="stretch",
            )

    top2 = standings[standings["pos"] <= 2]
    third = standings[standings["pos"] == 3].sort_values(["pts", "gd", "gf"], ascending=False)
    best8 = third.head(8)
    st.markdown("---")
    st.markdown(
        f"**Clasificados a eliminatorias:** "
        f"{len(top2)} primeros/segundos + {len(best8)} mejores terceros "
        f"= **{len(top2) + len(best8)} equipos**"
    )

# ────────────────────────────────────────────── ESTADÍSTICAS ─────────────────

with TAB_TEAMS:
    st.markdown(
        '<p style="color:#aaa;font-size:0.85rem;">'
        "Leyenda: PJ=Partidos · GF=Goles Favor · GC=Goles Contra · "
        "DG=Diferencia · Prom GF/PJ · Prom GC/PJ</p>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        metric = st.selectbox("Métrica", ["gd", "gf", "ga", "avg_gf", "avg_ga"],
                              format_func=lambda x: {
                                  "gd": "Diferencia de Gol (DG)",
                                  "gf": "Goles a Favor (GF)",
                                  "ga": "Goles en Contra (GC)",
                                  "avg_gf": "Promedio GF por partido",
                                  "avg_ga": "Promedio GC por partido",
                              }.get(x, x))
    with col2:
        top_n = st.slider("Mostrar top N", 5, 48, 15)

    top = teams.nlargest(top_n, metric)
    fig = px.bar(top, x="team", y=metric, color=metric,
                 color_continuous_scale="Greens", text=metric,
                 labels={"team": "Equipo", metric: {"gd": "DG", "gf": "GF",
                                                      "ga": "GC", "avg_gf": "Prom GF",
                                                      "avg_ga": "Prom GC"}.get(metric, metric)})
    fig.update_traces(textposition="outside")
    fig.update_layout(
        xaxis_title="", yaxis_title="",
        height=500, margin=dict(t=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#f0f0f0",
    )
    st.plotly_chart(fig, width="stretch")

# ────────────────────────────────────────────── PARTIDOS ─────────────────────

with TAB_MATCHES:
    round_opts = ["Todos"] + sorted(df["round"].unique().tolist())
    rnd = st.selectbox("Ronda", round_opts)
    team_opts = ["Todos"] + sorted(
        set(df["home_team"].unique()) | set(df["away_team"].unique())
    )
    tm = st.selectbox("Equipo", team_opts)

    filtered = match_log(df)
    if rnd != "Todos":
        filtered = filtered[filtered["round"] == rnd]
    if tm != "Todos":
        filtered = filtered[
            (filtered["home_team"] == tm) | (filtered["away_team"] == tm)
        ]

    st.dataframe(
        filtered.rename(columns={
            "match_utc": "Fecha (UTC)", "round": "Ronda",
            "group_name": "Grupo", "home_team": "Local",
            "score": "Marcador", "away_team": "Visitante",
        }),
        column_config={"Fecha (UTC)": st.column_config.DatetimeColumn(format="DD MMM, HH:mm")},
        hide_index=True,
        width="stretch",
    )

# ────────────────────────────────────────────── ELIMINATORIAS ────────────────

with TAB_KNOCKOUT:
    if bracket.empty:
        st.info("Aún no hay datos de eliminatorias.")
    else:
        for rnd_name in ["Round of 32", "Round of 16", "Quarter-Final",
                         "Semi-Final", "Third Place", "Final"]:
            matches = bracket[bracket["round"] == rnd_name]
            if matches.empty:
                continue

            st.markdown(f"#### {rnd_name.replace('-', ' ')}")
            cols = st.columns(min(len(matches), 4))

            for i, (_, m) in enumerate(matches.iterrows()):
                status = m["status"] if pd.notna(m["status"]) else "SCHEDULED"
                badge_class = {"FINISHED": "badge-played",
                               "IN_PLAY": "badge-live",
                               "SCHEDULED": "badge-scheduled"}.get(
                    status if status in ("FINISHED", "IN_PLAY") else "SCHEDULED",
                    "badge-scheduled"
                )
                home = m["home_team"] if "M#" not in str(m["home_team"]) else "Por definir"
                away = m["away_team"] if "M#" not in str(m["away_team"]) else "Por definir"

                with cols[i % len(cols)]:
                    st.markdown(
                        f'<div class="bracket-card">'
                        f'<div class="date">{m["date"]}</div>'
                        f'<div class="teams">{home} <span class="score">{m["score"]}</span> {away}</div>'
                        f'<div><span class="badge {badge_class}">{status}</span></div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            st.markdown("---")
