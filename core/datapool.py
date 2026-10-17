import sqlite3
import json
import hashlib
from datetime import datetime

DB_PATH = "datapool.db"

def _get_connection():
    """Connect to datapool database and ensure conversations and summaries tables exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            summary TEXT,
            keywords TEXT,
            embedding TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            summary TEXT,
            turn_start INTEGER,
            turn_end INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

def generate_session_id(schema_str: str) -> str:
    """Generate a unique 10-character session ID from the schema string using MD5."""
    return hashlib.md5(schema_str.encode()).hexdigest()[:10]

def save_message(session_id: str, role: str, content: str, keywords: list = [], embedding: list = []):
    """Save a single conversation message with its keywords and embedding to the datapool."""
    conn = _get_connection()
    conn.execute(
        '''INSERT INTO conversations 
           (session_id, role, content, keywords, embedding) 
           VALUES (?, ?, ?, ?, ?)''',
        (
            session_id,
            role,
            content,
            json.dumps(keywords),
            json.dumps(embedding)
        )
    )
    conn.commit()
    conn.close()

def get_all_messages(session_id: str) -> list:
    """Retrieve all messages for a session ordered by timestamp ascending."""
    conn = _get_connection()
    rows = conn.execute(
        '''SELECT role, content, keywords, embedding, timestamp 
           FROM conversations 
           WHERE session_id = ? 
           ORDER BY timestamp ASC''',
        (session_id,)
    ).fetchall()
    conn.close()
    return [
        {
            "role": row[0],
            "content": row[1],
            "keywords": json.loads(row[2]),
            "embedding": json.loads(row[3]),
            "timestamp": row[4]
        }
        for row in rows
    ]

def get_recent_messages(session_id: str, limit: int = 6) -> list:
    """Retrieve the most recent N messages for a session ordered oldest first."""
    conn = _get_connection()
    rows = conn.execute(
        '''SELECT role, content FROM conversations 
           WHERE session_id = ? 
           ORDER BY timestamp DESC LIMIT ?''',
        (session_id, limit)
    ).fetchall()
    conn.close()
    # reverse so oldest is first
    return [{"role": row[0], "content": row[1]} for row in reversed(rows)]

def save_summary(session_id: str, summary: str, turn_start: int, turn_end: int):
    """Save a compressed summary of a conversation chunk to the summaries table."""
    conn = _get_connection()
    conn.execute(
        '''INSERT INTO summaries (session_id, summary, turn_start, turn_end) 
           VALUES (?, ?, ?, ?)''',
        (session_id, summary, turn_start, turn_end)
    )
    conn.commit()
    conn.close()

def get_summaries(session_id: str) -> list:
    """Retrieve all summaries for a session ordered by turn start ascending."""
    conn = _get_connection()
    rows = conn.execute(
        '''SELECT summary, turn_start, turn_end FROM summaries 
           WHERE session_id = ? ORDER BY turn_start ASC''',
        (session_id,)
    ).fetchall()
    conn.close()
    return [{"summary": row[0], "turn_start": row[1], "turn_end": row[2]} for row in rows]

def count_messages(session_id: str) -> int:
    """Count total number of messages stored for a given session."""
    conn = _get_connection()
    count = conn.execute(
        'SELECT COUNT(*) FROM conversations WHERE session_id = ?',
        (session_id,)
    ).fetchone()[0]
    conn.close()
    return count