from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

TABLE = "fact_match"

_COLS = [
    "match_id", "season", "round", "matchday", "match_utc",
    "status", "home_team_id", "home_team", "away_team_id",
    "away_team", "home_goals", "away_goals", "group_name",
]


def load_matches(engine: Engine) -> pd.DataFrame:
    cols = ", ".join(_COLS)
    return pd.read_sql(
        f"SELECT {cols} FROM {TABLE} ORDER BY match_utc",
        engine,
        parse_dates=["match_utc"],
    )


def group_standings(df: pd.DataFrame) -> pd.DataFrame:
    """Group-stage standings: pos, group, team, pj, w, d, l, gf, ga, gd, pts."""
    groups = df[df["round"] == "GROUP_STAGE"].copy()
    if groups.empty:
        return pd.DataFrame()

    rows: list[dict] = []
    for _, m in groups.iterrows():
        for side, gs, gc in [
            ("home", m["home_goals"], m["away_goals"]),
            ("away", m["away_goals"], m["home_goals"]),
        ]:
            team = m[f"{side}_team"]
            w = 1 if gs > gc else 0
            d = 1 if gs == gc else 0
            l = 1 if gs < gc else 0
            rows.append({
                "group": m["group_name"],
                "team": team,
                "gf": gs, "ga": gc,
                "w": w, "d": d, "l": l,
                "pts": 3 * w + d,
            })

    agg = (
        pd.DataFrame(rows)
        .groupby(["group", "team"], as_index=False)
        .agg(pj=("pts", "count"), pts=("pts", "sum"),
             w=("w", "sum"), d=("d", "sum"), l=("l", "sum"),
             gf=("gf", "sum"), ga=("ga", "sum"))
    )
    agg["gd"] = agg["gf"] - agg["ga"]
    agg = agg.sort_values(["group", "pts", "gd", "gf"],
                          ascending=[True, False, False, False])
    agg["pos"] = agg.groupby("group").cumcount() + 1
    return agg[["pos", "group", "team", "pj", "w", "d", "l",
                "gf", "ga", "gd", "pts"]]


def team_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Per-team aggregates across all rounds."""
    rows: list[dict] = []
    for _, m in df.iterrows():
        rows.append({"team": m["home_team"], "gf": m["home_goals"],
                     "ga": m["away_goals"]})
        rows.append({"team": m["away_team"], "gf": m["away_goals"],
                     "ga": m["home_goals"]})

    agg = (
        pd.DataFrame(rows)
        .groupby("team", as_index=False)
        .agg(pj=("gf", "count"), gf=("gf", "sum"), ga=("ga", "sum"))
    )
    agg["gd"] = agg["gf"] - agg["ga"]
    agg["avg_gf"] = (agg["gf"] / agg["pj"]).round(2)
    agg["avg_ga"] = (agg["ga"] / agg["pj"]).round(2)
    return agg.sort_values("gd", ascending=False)[
        ["team", "pj", "gf", "ga", "gd", "avg_gf", "avg_ga"]
    ]


def match_log(df: pd.DataFrame) -> pd.DataFrame:
    """Readable match list for filtering / display."""
    out = df.copy()
    out["score"] = (out["home_goals"].astype(str) + " – "
                    + out["away_goals"].astype(str))
    return out[["match_utc", "round", "group_name",
                "home_team", "score", "away_team"]]


def knockout_matches(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to knockout rounds only."""
    return df[df["round"] != "GROUP_STAGE"].copy()
