"""SQLite audit logging service for Module 4.

Stores every evaluated event as a complete audit record including:
- All module inputs (RF context, threat intelligence, secure communication)
- All Module 4 outputs (risk score, trend, confidence, conflict, response)
- Full explanation reasons
- Timestamp and incident ID

Uses SQLite for the prototype. aiosqlite is available for async use,
but this implementation uses synchronous sqlite3 for simplicity.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from models.defense import EvaluateResponse

DB_PATH = Path(__file__).resolve().parents[1] / "database" / "incidents.db"

_incident_counter = 0


def get_next_incident_id() -> str:
    global _incident_counter
    _incident_counter += 1
    return f"INC-{str(_incident_counter).zfill(4)}"


def reset_counter() -> None:
    global _incident_counter
    _incident_counter = 0


def init_db() -> None:
    """Create the incidents table if it does not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id     TEXT PRIMARY KEY,
                timestamp       TEXT NOT NULL,
                observation_id  TEXT,

                -- Module 1 context
                rssi            REAL,
                snr             REAL,
                noise_floor     REAL,
                packet_rate     REAL,

                -- Module 2 context
                classification  TEXT,
                severity        TEXT,
                triggered_rule  TEXT,
                abnormal_features TEXT,
                evidence        TEXT,

                -- Module 3 context
                link_state      TEXT,
                freshness_state TEXT,
                auth_state      TEXT,
                integrity_state TEXT,
                replay_detected INTEGER,
                comm_decision   TEXT,

                -- Module 4 output
                risk_score      REAL,
                risk_level      TEXT,
                trend           TEXT,
                decision_confidence TEXT,
                evidence_conflict INTEGER,
                conflict_reason TEXT,
                recommended_response TEXT,
                response_status TEXT,
                reasons         TEXT,
                baseline_response TEXT,
                baseline_vs_proposed TEXT,

                -- Full JSON snapshot for audit
                full_response   TEXT
            )
        """)
        conn.commit()


def save_incident(response: EvaluateResponse) -> None:
    """Persist a Module 4 evaluation result to SQLite."""
    rf = response.module1_context
    ti = response.module2_context
    sc = response.module3_context

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO incidents VALUES (
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?
            )
        """, (
            response.incident_id,
            response.timestamp,
            response.observation_id,

            rf.get("rssi"),
            rf.get("snr"),
            rf.get("noise_floor"),
            rf.get("packet_rate"),

            ti.get("classification"),
            ti.get("severity"),
            ti.get("triggered_rule"),
            json.dumps(ti.get("abnormal_features", [])),
            json.dumps(ti.get("evidence", [])),

            sc.get("link_state"),
            sc.get("freshness_state"),
            sc.get("auth_state"),
            sc.get("integrity_state"),
            int(sc.get("replay_detected", False)),
            sc.get("comm_decision"),

            response.risk_score,
            response.risk_level,
            response.trend,
            response.decision_confidence,
            int(response.evidence_conflict),
            response.conflict_reason,
            response.recommended_response,
            response.response_status,
            json.dumps(response.reasons),
            response.baseline_response,
            response.baseline_vs_proposed,

            response.model_dump_json(),
        ))
        conn.commit()


def get_all_incidents(limit: int = 100) -> list[dict]:
    """Fetch incidents from SQLite ordered by incident_id ascending (INC-0001 first)."""
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM incidents ORDER BY incident_id ASC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_incident_by_id(incident_id: str) -> Optional[dict]:
    """Fetch a specific incident by ID from SQLite."""
    if not DB_PATH.exists():
        return None
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
        ).fetchone()
    return dict(row) if row else None


def get_risk_history(limit: int = 50) -> list[dict]:
    """Fetch recent risk scores ordered by incident_id ascending for trend visualization."""
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT incident_id, timestamp, risk_score, risk_level, trend, "
            "recommended_response, classification FROM incidents "
            "ORDER BY incident_id ASC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def clear_all() -> None:
    """Clear all incidents from the database (for simulation reset)."""
    global _incident_counter
    _incident_counter = 0
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM incidents")
            conn.commit()
