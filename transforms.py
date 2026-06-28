from __future__ import annotations

import pandas as pd
from sqlalchemy.engine import Engine

TABLE = "fact_match"

_COLS = [
    "match_id", "season", "round", "matchday", "match_utc",
    "status", "home_team_id", "home_team", "away_team_id",
    "away_team", "home_goals", "away_goals", "group_name",
]

R32 = [
    ("73",  "2026-06-28T19:00", "South Africa",       "Canada",              "SoFi Stadium"),
    ("74",  "2026-06-29T20:30", "Germany",            "Paraguay",            "Gillette Stadium"),
    ("75",  "2026-06-30T01:00", "Netherlands",        "Morocco",             "Estadio BBVA"),
    ("76",  "2026-06-29T17:00", "Brazil",             "Japan",               "NRG Stadium"),
    ("77",  "2026-06-30T21:00", "France",             "Sweden",              "MetLife Stadium"),
    ("78",  "2026-06-30T17:00", "Ivory Coast",        "Norway",              "AT&T Stadium"),
    ("79",  "2026-07-01T01:00", "Mexico",             "Ecuador",             "Estadio Azteca"),
    ("80",  "2026-07-01T16:00", "England",            "Congo DR",            "Mercedes-Benz Stadium"),
    ("81",  "2026-07-01T20:00", "Belgium",            "Senegal",             "Lumen Field"),
    ("82",  "2026-07-02T00:00", "United States",      "Bosnia-Herzegovina",  "Levi's Stadium"),
    ("83",  "2026-07-02T19:00", "Spain",              "Austria",             "SoFi Stadium"),
    ("84",  "2026-07-02T23:00", "Portugal",           "Croatia",             "BMO Field"),
    ("85",  "2026-07-03T03:00", "Switzerland",        "Algeria",             "BC Place"),
    ("86",  "2026-07-03T18:00", "Australia",          "Egypt",               "AT&T Stadium"),
    ("87",  "2026-07-03T22:00", "Argentina",          "Cape Verde Islands",  "Hard Rock Stadium"),
    ("88",  "2026-07-04T01:30", "Colombia",           "Ghana",               "Arrowhead Stadium"),
]

R16 = [
    ("89",  "2026-07-04", "74", "77"),
    ("90",  "2026-07-04", "73", "75"),
    ("91",  "2026-07-05", "76", "78"),
    ("92",  "2026-07-05", "79", "80"),
    ("93",  "2026-07-06", "84", "83"),
    ("94",  "2026-07-06", "82", "81"),
    ("95",  "2026-07-07", "87", "86"),
    ("96",  "2026-07-07", "85", "88"),
]

QF = [
    ("97",  "2026-07-09", "89", "90"),
    ("98",  "2026-07-10", "93", "94"),
    ("99",  "2026-07-11", "91", "92"),
    ("100", "2026-07-11", "95", "96"),
]

SF = [
    ("101", "2026-07-14", "97", "98"),
    ("102", "2026-07-15", "99", "100"),
]

THIRD_P = ("103", "2026-07-18", "101", "102")
FINAL_M = ("104", "2026-07-19", "101", "102")


def load_matches(engine: Engine) -> pd.DataFrame:
    cols = ", ".join(_COLS)
    df = pd.read_sql(
        f"SELECT {cols} FROM {TABLE} ORDER BY match_utc",
        engine,
        parse_dates=["match_utc"],
    )
    if not df.empty and df["match_utc"].dt.tz is None:
        df["match_utc"] = df["match_utc"].dt.tz_localize("UTC")
    return df


def group_standings(df: pd.DataFrame) -> pd.DataFrame:
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
    out = df.copy()
    out["score"] = (out["home_goals"].astype(str) + " – "
                    + out["away_goals"].astype(str))
    out["match_esp"] = out["match_utc"].dt.tz_convert("Europe/Madrid")
    return out[["match_utc", "match_esp", "round", "group_name",
                "home_team", "score", "away_team"]]


def _winner_of(played: pd.DataFrame, match_num: str) -> str | None:
    """Return the winner of a completed match, or None."""
    m = played[played["match_id"] == int(match_num)]
    if m.empty:
        return None
    r = m.iloc[0]
    if r["home_goals"] > r["away_goals"]:
        return r["home_team"]
    elif r["away_goals"] > r["home_goals"]:
        return r["away_team"]
    return None


def _loser_of(played: pd.DataFrame, match_num: str) -> str | None:
    m = played[played["match_id"] == int(match_num)]
    if m.empty:
        return None
    r = m.iloc[0]
    if r["home_goals"] < r["away_goals"]:
        return r["home_team"]
    elif r["away_goals"] < r["home_goals"]:
        return r["away_team"]
    return None


def _lookup(played: pd.DataFrame, home: str, away: str) -> dict | None:
    m = played[
        ((played["home_team"] == home) & (played["away_team"] == away))
        | ((played["home_team"] == away) & (played["away_team"] == home))
    ]
    if m.empty:
        return None
    r = m.iloc[0]
    return {
        "home_goals": int(r["home_goals"]),
        "away_goals": int(r["away_goals"]),
        "status": r["status"],
    }


def knockout_bracket(df: pd.DataFrame) -> pd.DataFrame:
    played = df[df["round"] != "GROUP_STAGE"]
    rows: list[dict] = []

    def add_match(num: str, date: str, home: str, away: str, rnd: str,
                  venue: str = "", src: str = ""):
        result = _lookup(played, home, away) if home and away else None
        rows.append({
            "round": rnd,
            "match": num,
            "date": date,
            "home_team": home,
            "away_team": away,
            "venue": venue,
            "home_goals": result["home_goals"] if result else None,
            "away_goals": result["away_goals"] if result else None,
            "status": result["status"] if result else "SCHEDULED",
            "src": src,
        })

    for num, date, home, away, venue in R32:
        add_match(num, date, home, away, "Round of 32", venue)

    def resolve(num: str) -> str:
        w = _winner_of(played, num)
        return w if w else f"R32 M#{num}"

    for num, date, src_a, src_b in R16:
        add_match(num, date, resolve(src_a), resolve(src_b), "Round of 16", f"{src_a}/{src_b}")

    for num, date, src_a, src_b in QF:
        a = resolve(src_a) if _winner_of(played, src_a) else f"R16 M#{src_a}"
        b = resolve(src_b) if _winner_of(played, src_b) else f"R16 M#{src_b}"
        add_match(num, date, a, b, "Quarter-Final", f"{src_a}/{src_b}")

    for num, date, src_a, src_b in SF:
        a = resolve(src_a) if _winner_of(played, src_a) else f"QF M#{src_a}"
        b = resolve(src_b) if _winner_of(played, src_b) else f"QF M#{src_b}"
        add_match(num, date, a, b, "Semi-Final", f"{src_a}/{src_b}")

    # Third place
    num, date, src_a, src_b = THIRD_P
    a = _loser_of(played, src_a) if _loser_of(played, src_a) else f"SF M#{src_a}"
    b = _loser_of(played, src_b) if _loser_of(played, src_b) else f"SF M#{src_b}"
    add_match(num, date, a, b, "Third Place", f"{src_a}/{src_b}")

    # Final
    num, date, src_a, src_b = FINAL_M
    a = resolve(src_a) if _winner_of(played, src_a) else f"SF M#{src_a}"
    b = resolve(src_b) if _winner_of(played, src_b) else f"SF M#{src_b}"
    add_match(num, date, a, b, "Final", f"{src_a}/{src_b}")

    result = pd.DataFrame(rows)
    result["score"] = result.apply(
        lambda r: f"{int(r['home_goals'])} – {int(r['away_goals'])}"
        if pd.notna(r["home_goals"]) else "vs",
        axis=1,
    )
    return result
