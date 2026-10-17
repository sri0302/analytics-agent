import sqlite3
import csv
import os

DB_PATH = "analytics.db"

def get_connection():
    """Get connection to the analytics database."""
    return sqlite3.connect(DB_PATH)

def load_csv_to_sqlite(path: str, table_name: str) -> str:
    """
    Load a CSV file into a SQLite table.
    Drops and recreates the table on each load.
    Returns the table name.
    """
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = reader.fieldnames

    if not rows or not headers:
        return ""

    # sanitize table and column names
    safe_table = table_name.replace("-", "_").replace(" ", "_").lower()
    safe_headers = [h.strip().replace(" ", "_").replace("-", "_").lower() for h in headers]

    conn = get_connection()

    # drop and recreate table
    conn.execute(f"DROP TABLE IF EXISTS {safe_table}")

    col_defs = ", ".join([f'"{col}" TEXT' for col in safe_headers])
    conn.execute(f"CREATE TABLE {safe_table} ({col_defs})")

    # insert all rows
    placeholders = ", ".join(["?" for _ in safe_headers])
    for row in rows:
        values = [row.get(h, "") for h in headers]
        conn.execute(
            f"INSERT INTO {safe_table} VALUES ({placeholders})",
            values
        )

    conn.commit()
    conn.close()

    return safe_table

def run_query(sql: str) -> dict:
    """
    Execute a SQL query and return results as a dict.
    Returns rows, columns, and row count.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()
        return {
            "success": True,
            "columns": columns,
            "rows": rows[:50],  # cap at 50 rows
            "total": len(rows)
        }
    except Exception as e:
        conn.close()
        return {
            "success": False,
            "error": str(e)
        }

def get_table_name() -> str:
    """Get the first table name in the analytics database."""
    conn = get_connection()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' LIMIT 1"
    ).fetchone()
    conn.close()
    return row[0] if row else ""