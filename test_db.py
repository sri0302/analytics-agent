from core.db_engine import get_connection, get_table_name

table = get_table_name()
print(f"Table name: {table}")

conn = get_connection()
count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
print(f"Total rows in SQLite: {count[0]}")

rows = conn.execute(f"SELECT * FROM {table} LIMIT 3").fetchall()
print(f"Sample rows: {rows}")
conn.close()