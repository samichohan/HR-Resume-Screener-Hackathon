"""
Persistence + HUMAN-IN-THE-LOOP
=================================
Every candidate row starts as hitl_status='pending'. The AI's
recommendation (match_probability + explanation) is only ever a
*suggestion* stored alongside it. The hitl_status field is changed in
exactly one place: update_hitl_decision(), which is only ever called from
the /api/hitl/<id> route in response to a recruiter clicking
Approve / Reject / Edit in the UI. The model never writes to this field.
"""
import os
import sqlite3
import json
import uuid
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "instance", "screening.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    candidate_name TEXT NOT NULL,
    target_category TEXT NOT NULL,
    match_probability REAL NOT NULL,
    category_confidence REAL NOT NULL,
    top_categories TEXT NOT NULL,
    components TEXT NOT NULL,
    xai_breakdown TEXT NOT NULL,
    matched_skills TEXT NOT NULL,
    missing_skills TEXT NOT NULL,
    years_experience REAL NOT NULL,
    ai_explanation TEXT NOT NULL,
    hitl_status TEXT NOT NULL DEFAULT 'pending',
    hitl_note TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    decided_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    job_description TEXT NOT NULL,
    target_category TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def create_session(job_description: str, target_category: str) -> str:
    session_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (id, job_description, target_category) VALUES (?, ?, ?)",
            (session_id, job_description, target_category),
        )
    return session_id


def insert_candidate(session_id: str, filename: str, candidate_name: str,
                      result: dict, ai_explanation: str,
                      matched_skills: list, missing_skills: list,
                      years_experience: float) -> str:
    candidate_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO candidates (
                id, session_id, filename, candidate_name, target_category,
                match_probability, category_confidence, top_categories,
                components, xai_breakdown, matched_skills, missing_skills,
                years_experience, ai_explanation, hitl_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (
                candidate_id, session_id, filename, candidate_name,
                result["target_category"], result["match_probability"],
                result["category_confidence"],
                json.dumps(result["top_categories"]),
                json.dumps(result["components"]),
                json.dumps(result["xai_rows"]),
                json.dumps(matched_skills), json.dumps(missing_skills),
                years_experience, ai_explanation,
            ),
        )
    return candidate_id


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for field in ("top_categories", "components", "xai_breakdown",
                  "matched_skills", "missing_skills"):
        d[field] = json.loads(d[field])
    return d


def get_candidates_by_session(session_id: str) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM candidates WHERE session_id = ? ORDER BY match_probability DESC",
            (session_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_candidate(candidate_id: str) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_session(session_id: str) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
    return dict(row) if row else None


def update_hitl_decision(candidate_id: str, decision: str, note: str = "") -> bool:
    """The ONLY function allowed to change hitl_status. Called exclusively
    from the human-triggered /api/hitl/<id> route."""
    if decision not in ("approved", "rejected", "edited"):
        raise ValueError(f"Invalid HITL decision: {decision}")
    with get_conn() as conn:
        cursor = conn.execute(
            """UPDATE candidates SET hitl_status = ?, hitl_note = ?,
               decided_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (decision, note, candidate_id),
        )
    return cursor.rowcount > 0
