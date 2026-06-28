"""
MVP ingestion: football-data.org (v4) -> CockroachDB.

Pulls FINISHED World Cup matches and upserts them into a `fact_match` table.
Idempotent by design (upsert on match_id), so it is safe to run on a schedule
(e.g. hourly during the knockout stage).

Switched from API-Football: its free plan only covers seasons 2022-2024, not
the live 2026 tournament. football-data.org's free tier DOES include the
World Cup, at the cost of delayed scores and no lineup/player data (so the
mplsoccer formation cameo is dropped — this script is aggregate-only now).

Free tier limit: 10 requests/minute (not a daily cap). One run = 1 request,
so this is nowhere near the limit even polled hourly.

This is the time-sensitive slice only. dbt models, the Streamlit dashboard and
the Airflow DAG come later and do NOT need to be ready to start capturing data.

Run:
    # .env (or exported env vars):
    #   FOOTBALL_DATA_TOKEN=your_free_token
    #   CRDB_HOST=esaldanaf-26570.j77.aws-eu-west-1.cockroachlabs.cloud
    #   CRDB_USER=esaldanaf
    #   CRDB_PASSWORD=your_password
    #   CRDB_DATABASE=worldcup
    python ingest_world_cup.py

Requirements:
    requests>=2.31  pydantic-settings>=2.0  python-dotenv>=1.0
    SQLAlchemy>=2.0  sqlalchemy-cockroachdb>=2.0  psycopg2-binary>=2.9
"""

from __future__ import annotations

import logging
import os

import requests
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import URL

# --- Config (secrets only via env / .env, never hardcoded) -------------------
#
# The DSN is NOT read as a single string. Building it from parts via
# URL.create() lets SQLAlchemy URL-encode the password safely (handles
# special characters like @ : / # that would otherwise break a raw DSN
# string) and keeps the password out of any logged/printed connection info.

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env" if os.path.isfile(".env") else None,
        extra="ignore",
    )

    football_data_token: str
    crdb_host: str
    crdb_user: str
    crdb_password: str
    crdb_database: str = "worldcup"
    crdb_port: int = 26257
    # "require" encrypts the connection but skips server identity verification.
    # Fine for local dev against your own cluster; upgrade to "verify-full" +
    # sslrootcert once the CA cert is downloaded for a production setup.
    crdb_sslmode: str = "require"
    base_url: str = "https://api.football-data.org/v4"
    competition_code: str = "WC"  # FIFA World Cup
    season_year: int = 2026
    request_delay_s: float = 6.5  # stay under the free plan's 10 req/min

    def build_dsn(self) -> URL:
        return URL.create(
            "cockroachdb+psycopg2",
            username=self.crdb_user,
            password=self.crdb_password,
            host=self.crdb_host,
            port=self.crdb_port,
            database=self.crdb_database,
            query={"sslmode": self.crdb_sslmode},
        )


# --- Logging -----------------------------------------------------------------

def get_logger(name: str = "ingest_wc") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


log = get_logger()
FINISHED_STATUS = "FINISHED"  # football-data.org's status enum for completed matches


# --- Schema (shared by ensure_schema and the upsert) -------------------------

metadata = MetaData()
fact_match = Table(
    "fact_match",
    metadata,
    Column("match_id", BigInteger, primary_key=True),
    Column("season", Integer, nullable=False),
    Column("round", String),       # e.g. "Group Stage", "Round of 16"
    Column("matchday", Integer),
    Column("match_utc", DateTime(timezone=True)),
    Column("status", String),
    Column("home_team_id", Integer),
    Column("home_team", String),
    Column("away_team_id", Integer),
    Column("away_team", String),
    Column("home_goals", Integer),
    Column("away_goals", Integer),
    Column("group_name", String),  # e.g. "Group A"; null for knockout matches
    Column("updated_at", DateTime(timezone=True), server_default=func.now()),
)


# --- Extract (only fetches raw data, no business logic) ----------------------

class FootballDataOrg:
    """Thin client for football-data.org v4. Free tier: 10 req/min, no auth scopes."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"X-Auth-Token": settings.football_data_token})

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = self.session.get(
            f"{self.settings.base_url}{path}", params=params or {}, timeout=20
        )
        if resp.status_code == 429:
            raise RuntimeError("HTTP 429 — rate limit hit (10 req/min on free tier).")
        resp.raise_for_status()
        return resp.json()

    def finished_matches(self) -> list[dict]:
        """Return raw finished-match dicts for the configured competition/season."""
        payload = self._get(
            f"/competitions/{self.settings.competition_code}/matches",
            {"season": self.settings.season_year, "status": FINISHED_STATUS},
        )
        return payload.get("matches", [])


# --- Transform (pure function, no I/O) ---------------------------------------

def to_fact_row(raw: dict, season: int) -> dict:
    score = raw["score"]["fullTime"]
    return {
        "match_id": raw["id"],
        "season": season,
        "round": raw.get("stage"),
        "matchday": raw.get("matchday"),
        "match_utc": raw["utcDate"],
        "status": raw["status"],
        "home_team_id": raw["homeTeam"]["id"],
        "home_team": raw["homeTeam"]["name"],
        "away_team_id": raw["awayTeam"]["id"],
        "away_team": raw["awayTeam"]["name"],
        "home_goals": score["home"],
        "away_goals": score["away"],
        "group_name": raw.get("group"),
    }


# --- Load (idempotent upsert; the only place that writes) --------------------

def upsert_matches(engine, rows: list[dict]) -> None:
    if not rows:
        log.info("No finished matches to load yet.")
        return
    stmt = insert(fact_match).values(rows)
    update_cols = {
        c.name: stmt.excluded[c.name]
        for c in fact_match.columns
        if c.name != "match_id"
    }
    update_cols["updated_at"] = func.now()
    stmt = stmt.on_conflict_do_update(index_elements=["match_id"], set_=update_cols)
    with engine.begin() as conn:
        conn.execute(stmt)


# --- Orchestration -----------------------------------------------------------

def main() -> None:
    settings = Settings()  # raises clearly if env vars are missing
    engine = create_engine(settings.build_dsn())
    metadata.create_all(engine)  # create fact_match if it does not exist

    api = FootballDataOrg(settings)
    raw = api.finished_matches()
    rows = [to_fact_row(r, settings.season_year) for r in raw]
    upsert_matches(engine, rows)
    log.info("Upserted %s finished matches into fact_match.", len(rows))


if __name__ == "__main__":
    main()