# ↑ memory cache (SQLite)

import sqlite3
import hashlib
import os

DB_PATH = "cache.db"


def _get_connection():
    """Create or return a connection to the analytics SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            query TEXT,
            response TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

def make_key(schema_str: str, query: str) -> str:
    """
    Generate a unique MD5 hash key from schema and query for cache lookup
    """
    combined = schema_str + query.strip().lower()
    return hashlib.md5(combined.encode()).hexdigest()

def get_cached(schema_str: str, query: str) -> str | None:
    '''
    Look up a cached response by schema and query. Returns None if not found
    '''
    key = make_key(schema_str, query)
    conn = _get_connection()
    row = conn.execute(
        'SELECT response FROM cache WHERE key = ?', (key,)
    ).fetchone()
    conn.close()
    return row[0] if row else None




def save_to_cache(schema_str: str, query: str, response: str):
    '''
    save every latest response to the cache to reduce response time
    '''
    key = make_key(schema_str, query)
    conn = _get_connection()
    conn.execute(
        'INSERT OR REPLACE INTO cache (key, query, response) VALUES (?, ?, ?)',
        (key, query, response)
    )
    conn.commit()
    conn.close()