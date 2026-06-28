from __future__ import annotations

import pandas as pd
import streamlit as st
import plotly.express as px
from sqlalchemy import create_engine

from ingest_world_cup import Settings
from transforms import load_matches, group_standings, team_stats, match_log, knockout_bracket

st.set_page_config(page_title="World Cup 2026", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    * { font-family: 'Inter', -apple-system, sans-serif; }

    .stApp {
        background: #111118;
    }

    h1, h2, h3, h4, label, .stMarkdown, .stDataFrame,
    .stSelectbox label, .stSlider label {
        color: #e8e8ef !important;
    }

    h1 {
        font-weight: 700;
        font-size: 2rem;
        letter-spacing: -0.5px;
        background: linear-gradient(135deg, #00e676, #00bcd4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .subtitle {
        color: #888;
        font-size: 0.9rem;
        margin-top: -8px;
        margin-bottom: 24px;
    }

    .stTabs [data-baseweb="tab-list"] {
        background: #1e1e28;
        border-radius: 10px;
        padding: 4px;
        gap: 2px;
        border: 1px solid #2a2a38;
    }

    .stTabs [data-baseweb="tab-list"] button {
        border-radius: 8px !important;
        background: transparent !important;
        color: #888 !important;
        font-weight: 500;
        font-size: 0.85rem;
        padding: 6px 18px;
    }

    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        background: #2a2a3a !important;
        color: #00e676 !important;
    }

    .stDataFrame {
        background: transparent !important;
    }

    .stDataFrame thead tr th {
        background: #1a1a25 !important;
        color: #00e676 !important;
        font-weight: 600;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 2px solid #2a2a3a;
    }

    .stDataFrame tbody tr td {
        background: transparent !important;
        color: #d0d0dd !important;
        border-bottom: 1px solid #1e1e2a;
    }

    .stDataFrame tbody tr:hover td {
        background: #1a1a28 !important;
    }

    .st-bb, .st-at {
        background-color: transparent !important;
    }

    .legend {
        color: #666;
        font-size: 0.8rem;
        margin-bottom: 16px;
        padding: 8px 14px;
        background: #1a1a25;
        border-radius: 8px;
        border: 1px solid #2a2a38;
    }

    .stExpander {
        background: #181820;
        border: 1px solid #2a2a38;
        border-radius: 10px;
        margin-bottom: 10px;
    }

    .stExpander summary {
        font-weight: 600;
        color: #e0e0ef;
    }

    .match-card {
        background: #181820;
        border: 1px solid #2a2a38;
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 10px;
        transition: border-color 0.2s;
    }

    .match-card:hover {
        border-color: #00e67655;
    }

    .match-card .teams {
        font-size: 1rem;
        font-weight: 500;
        color: #e8e8ef;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .match-card .score {
        font-size: 1.3rem;
        font-weight: 700;
        color: #ffd740;
        margin: 0 16px;
        min-width: 48px;
        text-align: center;
    }

    .match-card .meta {
        font-size: 0.78rem;
        color: #777;
        margin-top: 6px;
        display: flex;
        gap: 16px;
        align-items: center;
    }

    .match-card .meta .dot {
        width: 4px; height: 4px;
        border-radius: 50%;
        background: #555;
        display: inline-block;
    }

    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.3px;
    }

    .badge-finished {
        background: #00e67622;
        color: #00e676;
        border: 1px solid #00e67644;
    }

    .badge-scheduled {
        background: #44446622;
        color: #8888aa;
        border: 1px solid #44446644;
    }

    .badge-live {
        background: #ffd74022;
        color: #ffd740;
        border: 1px solid #ffd74044;
    }

    .round-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #ccccee;
        margin: 20px 0 12px 0;
        padding-bottom: 6px;
        border-bottom: 2px solid #2a2a3a;
    }

    .stSidebar {
        background: #181820;
        border-right: 1px solid #2a2a38;
    }

    .stSidebar label {
        color: #aaa !important;
        font-size: 0.8rem;
    }

    hr {
        border-color: #2a2a38 !important;
        margin: 8px 0;
    }

    .stSelectbox>div>div {
        background: #1e1e28 !important;
        border: 1px solid #2a2a38 !important;
        color: #e8e8ef !important;
        border-radius: 8px !important;
    }

    .stSlider>div>div>div {
        background: #00e676 !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("# World Cup 2026")
st.markdown('<p class="subtitle">Tabla de posiciones · Estadísticas · Eliminatorias</p>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("**Preferencias**")
    tz = st.selectbox("Horario", ["UTC", "España (CEST)"], index=1)
    show_es = tz == "España (CEST)"

engine = create_engine(Settings().build_dsn())

TAB_GROUPS, TAB_TEAMS, TAB_MATCHES, TAB_KNOCKOUT = st.tabs([
    "Posiciones", "Estadísticas", "Partidos", "Eliminatorias",
])


@st.cache_data(ttl=300)
def get_data():
    df = load_matches(engine)
    return df, group_standings(df), team_stats(df), knockout_bracket(df)


df, standings, teams, bracket = get_data()

if show_es:
    tz_name = "Europe/Madrid"
    tz_label = "CEST"
else:
    tz_name = "UTC"
    tz_label = "UTC"

last_refresh = pd.Timestamp.now(tz=tz_name)

with st.sidebar:
    st.markdown("---")
    st.markdown(
        f'<p style="color:#666;font-size:0.75rem;">'
        f"Última actualización: {last_refresh.strftime('%d %b, %H:%M')} {tz_label}"
        f"</p>",
        unsafe_allow_html=True,
    )
    if st.button("Actualizar ahora", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ────────────────────────────────────────────── POSICIONES ────────────────────

with TAB_GROUPS:
    st.markdown(
        '<div class="legend">'
        "PJ = Partidos · PG = Ganados · PE = Empatados · PP = Perdidos · "
        "GF = Goles Favor · GC = Goles Contra · DG = Diferencia · Pts = Puntos"
        "</div>",
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
                column_config={"DG": st.column_config.NumberColumn(format="%+d")},
                hide_index=False, width="stretch",
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
        '<div class="legend">'
        "PJ = Partidos · GF = Goles Favor · GC = Goles Contra · "
        "DG = Diferencia · Prom GF = Promedio de goles por partido"
        "</div>",
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
                 color_continuous_scale="Tealgrn", text=metric,
                 labels={"team": "Equipo", metric: {
                     "gd": "DG", "gf": "GF", "ga": "GC",
                     "avg_gf": "Prom GF", "avg_ga": "Prom GC",
                 }.get(metric, metric)})
    fig.update_traces(textposition="outside", textfont_color="#e0e0e0")
    fig.update_layout(
        xaxis_title="", yaxis_title="",
        height=500, margin=dict(t=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#d0d0dd",
        xaxis={"tickangle": -45},
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

    display = filtered.copy()
    if show_es:
        display["hora"] = display["match_esp"].dt.strftime("%d %b, %H:%M")
    else:
        display["hora"] = display["match_utc"].dt.strftime("%d %b, %H:%M")
    display = display.rename(columns={
        "round": "Ronda", "group_name": "Grupo",
        "home_team": "Local", "score": "Marcador", "away_team": "Visitante",
    })
    tz_label = "CEST" if show_es else "UTC"
    st.dataframe(
        display[["hora", "Ronda", "Grupo", "Local", "Marcador", "Visitante"]].rename(
            columns={"hora": f"Fecha ({tz_label})"}
        ),
        hide_index=True, width="stretch",
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

            st.markdown(f'<div class="round-header">{rnd_name.replace("-", " ")}</div>',
                        unsafe_allow_html=True)
            cols = st.columns(min(len(matches), 4))

            for i, (_, m) in enumerate(matches.iterrows()):
                status = m["status"] if pd.notna(m["status"]) else "SCHEDULED"
                badge_cls = "badge-finished" if status == "FINISHED" else (
                    "badge-live" if status == "IN_PLAY" else "badge-scheduled")

                home = m["home_team"] if "M#" not in str(m["home_team"]) else "—"
                away = m["away_team"] if "M#" not in str(m["away_team"]) else "—"

                # Format time
                try:
                    dt = pd.Timestamp(m["date"]).tz_localize("UTC")
                    if show_es:
                        dt = dt.tz_convert("Europe/Madrid")
                    time_str = dt.strftime("%d %b, %H:%M")
                except Exception:
                    time_str = m["date"]

                venue = m.get("venue", "")
                venue_str = f" · {venue}" if venue else ""

                with cols[i % len(cols)]:
                    st.markdown(
                        f'<div class="match-card">'
                        f'<div class="teams">'
                        f'<span>{home}</span>'
                        f'<span class="score">{m["score"]}</span>'
                        f'<span>{away}</span>'
                        f'</div>'
                        f'<div class="meta">'
                        f'<span>{time_str}</span>'
                        f'<span class="dot"></span>'
                        f'<span class="badge {badge_cls}">{status}</span>'
                        f'<span class="dot"></span>'
                        f'<span>{venue_str}</span>'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            st.markdown("---")
