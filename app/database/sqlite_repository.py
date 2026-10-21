"""SQLite repository supporting multiple gyms."""

import json
import sqlite3

from flask import current_app
from app.services.inventory_service import initial_state


def connect():
    db = sqlite3.connect(
        current_app.config["DATABASE"],
        timeout=15
    )

    db.execute("""
        CREATE TABLE IF NOT EXISTS gym_state (
            gym_id TEXT PRIMARY KEY,
            document TEXT NOT NULL
        )
    """)

    # Preserve data from the original single-gym database.
    old_table = db.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name = 'app_state'
    """).fetchone()

    if old_table:
        old_row = db.execute("""
            SELECT document FROM app_state WHERE id = 1
        """).fetchone()

        if old_row:
            db.execute("""
                INSERT OR IGNORE INTO gym_state (gym_id, document)
                VALUES (?, ?)
            """, ("gym-a", old_row[0]))

    db.commit()
    return db


def get_state(gym_id="gym-a"):
    with connect() as db:
        row = db.execute("""
            SELECT document
            FROM gym_state
            WHERE gym_id = ?
        """, (gym_id,)).fetchone()

        if row:
            return json.loads(row[0])

        state = initial_state()

        db.execute("""
            INSERT OR IGNORE INTO gym_state (gym_id, document)
            VALUES (?, ?)
        """, (gym_id, json.dumps(state)))

        # Read the persisted record in case another request created it.
        row = db.execute("""
            SELECT document FROM gym_state WHERE gym_id = ?
        """, (gym_id,)).fetchone()

        return json.loads(row[0])


def save_state(state, gym_id="gym-a"):
    with connect() as db:
        db.execute("""
            INSERT INTO gym_state (gym_id, document)
            VALUES (?, ?)
            ON CONFLICT(gym_id)
            DO UPDATE SET document = excluded.document
        """, (gym_id, json.dumps(state)))