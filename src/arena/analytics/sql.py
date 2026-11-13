"""The ledger as SQL tables (DuckDB) and as open-data Parquet files.

Owner request 2026-11-12 (docs/project/DECISIONS.md "Open data and SQL analytics"). Everything is
derived from the ledger by code (I5); the site shows each query next to its result so a
reader can rerun it. These analyses are exploratory; the headline results stay on the
leaderboard (SPEC 10), which is computed by `arena.scoring`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from arena.scoring.core import CLIP_HIGH, CLIP_LOW

TABLES: dict[str, str] = {
    "questions": (
        "question_id VARCHAR, domain VARCHAR, template VARCHAR, entity VARCHAR, "
        "batch_date DATE, target_date DATE, threshold DOUBLE, text VARCHAR"
    ),
    "forecasts": (
        "question_id VARCHAR, forecaster_id VARCHAR, forecaster_version VARCHAR, "
        "probability DOUBLE, created_at TIMESTAMPTZ"
    ),
    "resolutions": "question_id VARCHAR, outcome INTEGER, observed_value DOUBLE",
    "skips": "question_id VARCHAR, forecaster_id VARCHAR, reason_code VARCHAR",
}


@dataclass(frozen=True)
class Query:
    """A named SQL query shown on the site."""

    slug: str
    title: str
    why: str
    sql: str


QUERIES: tuple[Query, ...] = (
    Query(
        "brier-by-forecaster-domain",
        "Mean Brier score by forecaster and topic",
        "Proper scoring rule on clipped probabilities, per topic. Lower is better.",
        f"""SELECT q.domain, f.forecaster_id,
       count(*) AS n,
       round(avg(power(least(greatest(f.probability, {CLIP_LOW}), {CLIP_HIGH})
                       - r.outcome, 2)), 4) AS brier
FROM forecasts f
JOIN resolutions r USING (question_id)
JOIN questions q USING (question_id)
GROUP BY ALL
ORDER BY q.domain, brier""",
    ),
    Query(
        "yes-rate-by-template",
        "How often the answer was YES, per question type",
        "Base rates: question templates are designed to be neither almost-always YES nor NO.",
        """SELECT q.domain, q.template,
       count(*) AS resolved,
       round(avg(r.outcome), 3) AS yes_rate
FROM questions q
JOIN resolutions r USING (question_id)
GROUP BY ALL
ORDER BY q.domain, q.template""",
    ),
    Query(
        "sharpness",
        "How bold is each forecaster?",
        "Mean distance of the forecast from 50% (sharpness). Bold and right is good; bold "
        "and wrong is punished by the Brier score.",
        """SELECT forecaster_id,
       count(*) AS forecasts,
       round(avg(abs(probability - 0.5)), 3) AS mean_distance_from_50,
       round(avg(probability), 3) AS mean_probability
FROM forecasts
GROUP BY ALL
ORDER BY mean_distance_from_50 DESC""",
    ),
    Query(
        "skips",
        "Recorded skips by forecaster and reason",
        "A failure is recorded as a skip with a reason, never replaced by a guess.",
        """SELECT forecaster_id, reason_code, count(*) AS skips
FROM skips
GROUP BY ALL
ORDER BY skips DESC, forecaster_id""",
    ),
)


#: Data dictionary (T138): every column of every exported table, in plain words.
COLUMN_DOCS: dict[str, dict[str, str]] = {
    "questions": {
        "question_id": "Unique id: domain-template-entity-target date-template version",
        "domain": "Topic: power, weather, attention, markets or crypto",
        "template": "The question rule it was made from, e.g. mean_gt",
        "entity": "What it is about, e.g. DE_LU (the electricity zone) or a city",
        "batch_date": "Day the question was asked (UTC); forecasts lock 09:30 UTC that day",
        "target_date": "Day the question is about",
        "threshold": "The number in the question (empty when the question compares two days)",
        "text": "The full question as published",
    },
    "forecasts": {
        "question_id": "Which question",
        "forecaster_id": "Who answered, e.g. base_rate, ml, llm_context, agent",
        "forecaster_version": "Exact model and prompt version that produced it",
        "probability": "Published probability of YES, between 0 and 1 (raw, not clipped)",
        "created_at": "When it was written; always before the question's lock time",
    },
    "resolutions": {
        "question_id": "Which question",
        "outcome": "1 = YES, 0 = NO (the first recorded resolution)",
        "observed_value": "The measured value the outcome was computed from",
    },
    "skips": {
        "question_id": "Which question",
        "forecaster_id": "Who did not answer",
        "reason_code": "Why: not_sampled, budget_exhausted, parse_failure, model_missing, error",
    },
}


def _insert(con: duckdb.DuckDBPyConnection, table: str, rows: list[tuple[Any, ...]]) -> None:
    """Insert rows; an empty ledger simply leaves the table empty."""
    if rows:
        marks = ", ".join("?" * len(rows[0]))
        con.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)


def connect(rec: Any) -> duckdb.DuckDBPyConnection:
    """An in-memory DuckDB database holding the ledger's tables."""
    con = duckdb.connect(":memory:")
    for name, cols in TABLES.items():
        con.execute(f"CREATE TABLE {name} ({cols})")
    qs = rec.questions.values()
    _insert(
        con,
        "questions",
        [
            (
                q.question_id,
                q.domain,
                q.template,
                q.entity,
                q.batch_date,
                q.target_date,
                q.threshold,
                q.text,
            )
            for q in qs
        ],
    )
    _insert(
        con,
        "forecasts",
        [
            (f.question_id, f.forecaster_id, f.forecaster_version, f.probability, f.created_at)
            for f in rec.forecasts
        ],
    )
    _insert(
        con,
        "resolutions",
        [(r.question_id, r.outcome, r.observed_value) for r in rec.resolutions.values()],
    )
    _insert(
        con,
        "skips",
        [(s.question_id, s.forecaster_id, s.reason_code) for s in rec.skips],
    )
    return con


def run_queries(con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Each query with its column names and rows."""
    out = []
    for q in QUERIES:
        cur = con.execute(q.sql)
        cols = [d[0] for d in cur.description]
        out.append({"q": q, "columns": cols, "rows": cur.fetchall()})
    return out


def export_parquet(con: duckdb.DuckDBPyConnection, out_dir: Path) -> list[str]:
    """Write every table as `<name>.parquet` (zstd) into `out_dir`; returns the file names."""
    out_dir.mkdir(parents=True, exist_ok=True)
    names = []
    for name in TABLES:
        path = out_dir / f"{name}.parquet"
        con.execute(f"COPY {name} TO '{path.as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
        names.append(path.name)
    return names


def column_types() -> dict[str, dict[str, str]]:
    """SQL type of every column, from `TABLES` (for the data dictionary)."""
    out: dict[str, dict[str, str]] = {}
    for table, cols in TABLES.items():
        for part in cols.split(","):
            name, typ = part.strip().split(" ", 1)
            out.setdefault(table, {})[name] = typ
    return out


_REF = re.compile(r"\{\{\s*ref\('([a-z_]+)'\)\s*\}\}")


def run_dbt_marts(
    con: duckdb.DuckDBPyConnection, marts_dir: Path | None, limit: int = 50
) -> list[dict[str, Any]]:
    """Execute the dbt mart models (T152) on the site's tables, so the Data page shows the
    same definitions that `dbt build` runs and tests in CI. `ref('stg_x')` is the table
    `x` (the staging models are plain selects); other refs are earlier models, created as
    views first (fct_* before mart_*)."""
    if marts_dir is None or not marts_dir.is_dir():
        return []
    files = sorted(marts_dir.glob("*.sql"), key=lambda p: (not p.stem.startswith("fct_"), p.stem))
    out = []
    for f in files:
        body = f.read_text(encoding="utf-8")
        sql = _REF.sub(lambda m: m.group(1).removeprefix("stg_"), body)
        sql = "\n".join(ln for ln in sql.splitlines() if not ln.lstrip().startswith("--"))
        con.execute(f"CREATE OR REPLACE VIEW {f.stem} AS {sql}")
        if f.stem.startswith("mart_"):
            cur = con.execute(f"SELECT * FROM {f.stem} ORDER BY ALL LIMIT {limit}")
            cols = [d[0] for d in cur.description or []]
            doc = next((ln[2:].strip() for ln in body.splitlines() if ln.startswith("--")), "")
            out.append(
                {
                    "name": f.stem,
                    "doc": doc,
                    "columns": cols,
                    "rows": cur.fetchall(),
                    "source": f"analytics/dbt/models/marts/{f.name}",
                }
            )
    return out
