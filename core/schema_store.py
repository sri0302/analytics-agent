import sqlite3
import json

DB_PATH = "schema_store.db"

def _get_connection():
    """Create or connect to schema store database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
    CREATE TABLE IF NOT EXISTS schema_state (
        id INTEGER PRIMARY KEY,
        schema TEXT,
        masked TEXT,
        joins TEXT,
        sample_rows TEXT,
        schema_str TEXT,
        session_id TEXT,
        total_rows INTEGER,
        total_cols INTEGER,
        table_name TEXT,
        loaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
         )
    ''')
    conn.commit()
    return conn

def save_schema(state: dict):
    """Persist current schema state to SQLite."""
    conn = _get_connection()
    conn.execute("DELETE FROM schema_state")  # only keep latest
    conn.execute(
    '''INSERT INTO schema_state 
       (schema, masked, joins, sample_rows, schema_str, session_id, total_rows, total_cols, table_name)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
    (
        json.dumps(state["schema"]),
        json.dumps(state["masked"]),
        json.dumps(state["joins"]),
        json.dumps(state["sample_rows"]),
        state["schema_str"],
        state["session_id"],
        state["total_rows"],
        state["total_cols"],
        state.get("table_name", "")
    )
)
    conn.commit()
    conn.close()

def load_schema() -> dict | None:
    """Load last saved schema state from SQLite. Returns None if nothing saved."""
    conn = _get_connection()
    row = conn.execute(
        '''SELECT schema, masked, joins, sample_rows, schema_str, 
           session_id, total_rows, total_cols,table_name, loaded_at
           FROM schema_state ORDER BY loaded_at DESC LIMIT 1'''
    ).fetchone()
    conn.close()

    if not row:
        return None

    return {
        "schema": json.loads(row[0]),
        "masked": json.loads(row[1]),
        "joins": json.loads(row[2]),
        "sample_rows": json.loads(row[3]),
        "schema_str": row[4],
        "session_id": row[5],
        "total_rows": row[6],
        "total_cols": row[7],
         "table_name": row[8],
        "loaded_at": row[9]
    }

def clear_schema():
    """Wipe saved schema — used when user wants to load a fresh one."""
    conn = _get_connection()
    conn.execute("DELETE FROM schema_state")
    conn.commit()
    conn.close()