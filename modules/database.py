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


# ---------------------------------------------------------------------------
# READ-ONLY helpers for the dashboard / history / search / compare UI.
# None of these can write to hitl_status — they only ever SELECT.
# ---------------------------------------------------------------------------

def get_all_sessions() -> list:
    """Every past screening session, newest first, with a candidate count."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT s.id, s.job_description, s.target_category, s.created_at,
                      COUNT(c.id) AS candidate_count,
                      AVG(c.match_probability) AS avg_score
               FROM sessions s
               LEFT JOIN candidates c ON c.session_id = s.id
               GROUP BY s.id
               ORDER BY s.created_at DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_candidates(search: str = "", status: str = "", category: str = "",
                        session_id: str = "") -> list:
    """Every candidate ever screened, across all sessions, with optional
    filters — used by Candidate History, Search & Filter, and Compare."""
    query = """SELECT c.*, s.job_description AS session_job_description
               FROM candidates c
               JOIN sessions s ON s.id = c.session_id
               WHERE 1=1"""
    params = []
    if search:
        query += " AND (c.candidate_name LIKE ? OR c.filename LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if status:
        query += " AND c.hitl_status = ?"
        params.append(status)
    if category:
        query += " AND c.target_category = ?"
        params.append(category)
    if session_id:
        query += " AND c.session_id = ?"
        params.append(session_id)
    query += " ORDER BY c.created_at DESC"

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_dashboard_stats() -> dict:
    """All-time aggregate stats for the live dashboard."""
    with get_conn() as conn:
        totals = conn.execute(
            """SELECT COUNT(*) AS total_candidates,
                      AVG(match_probability) AS avg_score,
                      SUM(CASE WHEN hitl_status='approved' THEN 1 ELSE 0 END) AS approved,
                      SUM(CASE WHEN hitl_status='rejected' THEN 1 ELSE 0 END) AS rejected,
                      SUM(CASE WHEN hitl_status='edited' THEN 1 ELSE 0 END) AS edited,
                      SUM(CASE WHEN hitl_status='pending' THEN 1 ELSE 0 END) AS pending
               FROM candidates"""
        ).fetchone()

        total_sessions = conn.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()["n"]

        by_category = conn.execute(
            """SELECT target_category, COUNT(*) AS n, AVG(match_probability) AS avg_score
               FROM candidates GROUP BY target_category ORDER BY n DESC"""
        ).fetchall()

        # score distribution buckets for a histogram
        buckets = conn.execute(
            """SELECT
                 SUM(CASE WHEN match_probability < 0.2 THEN 1 ELSE 0 END) AS b0,
                 SUM(CASE WHEN match_probability >= 0.2 AND match_probability < 0.4 THEN 1 ELSE 0 END) AS b1,
                 SUM(CASE WHEN match_probability >= 0.4 AND match_probability < 0.6 THEN 1 ELSE 0 END) AS b2,
                 SUM(CASE WHEN match_probability >= 0.6 AND match_probability < 0.8 THEN 1 ELSE 0 END) AS b3,
                 SUM(CASE WHEN match_probability >= 0.8 THEN 1 ELSE 0 END) AS b4
               FROM candidates"""
        ).fetchone()

        recent = conn.execute(
            """SELECT c.id, c.candidate_name, c.target_category, c.match_probability,
                      c.hitl_status, c.created_at, c.session_id
               FROM candidates c ORDER BY c.created_at DESC LIMIT 8"""
        ).fetchall()

    return {
        "total_candidates": totals["total_candidates"] or 0,
        "total_sessions": total_sessions or 0,
        "avg_score": round(totals["avg_score"], 4) if totals["avg_score"] else 0,
        "approved": totals["approved"] or 0,
        "rejected": totals["rejected"] or 0,
        "edited": totals["edited"] or 0,
        "pending": totals["pending"] or 0,
        "by_category": [dict(r) for r in by_category],
        "score_distribution": {
            "0-20%": buckets["b0"] or 0, "20-40%": buckets["b1"] or 0,
            "40-60%": buckets["b2"] or 0, "60-80%": buckets["b3"] or 0,
            "80-100%": buckets["b4"] or 0,
        },
        "recent_activity": [dict(r) for r in recent],
    }
