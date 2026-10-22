from core.schema_store import save_schema, load_schema, clear_schema
from core.db_engine import load_csv_to_sqlite, run_query, get_table_name
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.request
import urllib.error
import os
import webbrowser
import threading
from dotenv import load_dotenv
from ingestion.parser import parse_sql
from ingestion.csv_loader import load_csv
from core.masker import mask_schema
from core.joiner import detect_joins
from core.guard import validate_query
from core.cache import get_cached, save_to_cache
from core.datapool import generate_session_id, save_message, get_recent_messages, get_summaries
from core.retriever import retrieve_relevant, extract_keywords
from core.summariser import should_summarise, summarise_session

load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
file_path = os.path.abspath("index.html")

state = {
    "schema": {},
    "masked": {},
    "joins": [],
    "sample_rows": [],
    "schema_str": "",
    "session_id": "",
    "total_rows": 0,
    "total_cols": 0,
    "table_name": ""
}

BYPASS_PATTERNS = [
    "how many", "count", "rows", "columns", "total",
    "list", "show me", "what are the", "describe",
    "summarise", "summarize", "overview"
]

ANALYTICAL_PATTERNS = [
    "most", "least", "top", "bottom", "best", "worst",
    "popular", "average", "avg", "sum", "highest", "lowest",
    "rank", "percent", "ratio", "distribution", "which", "compare"
]

GREETINGS = ["hi", "hello", "hey", "yo", "thanks", "thank", "bye"]

PERSONA = (
    "You are a friendly data analyst with a dry, light sense of humour. "
    "Keep a casual tone with occasional playful sarcasm, "
    "but never at the expense of accuracy. "
)

def is_greeting(query: str) -> bool:
    """Check if the query is a short greeting or pleasantry rather than a data question."""
    words = [w.strip("!,.?") for w in query.lower().split()]
    return len(words) <= 4 and any(w in GREETINGS for w in words)

def should_bypass_cache(query: str) -> bool:
    """Check if query should skip cache and always hit API fresh."""
    q = query.lower()
    if is_greeting(q):
        return True
    return any(pattern in q for pattern in BYPASS_PATTERNS + ANALYTICAL_PATTERNS)

def needs_sql(query: str) -> bool:
    """Check if query needs SQL execution against full dataset."""
    q = query.lower()
    return any(pattern in q for pattern in ANALYTICAL_PATTERNS)

def clean_sql(raw: str) -> str:
    """Strip markdown code fences GPT sometimes wraps around generated SQL."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.lower().startswith("sql"):
            raw = raw[3:]
    return raw.strip()

def generate_and_run_sql(query: str, schema_context: str, table_name: str) -> str:
    """
    Two-step pipeline:
    1. Ask GPT to generate SQL from the question.
    2. Execute SQL against SQLite.
    3. Ask GPT to explain results in plain English.
    """
    # step 1 — generate SQL (no persona here, SQL must be clean)
    sql_payload = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": (
                    f"You are a SQL expert. Given this schema:\n{schema_context}\n\n"
                    f"The data is stored in a SQLite table called '{table_name}'. "
                    "Generate ONLY a valid SQLite SELECT query to answer the user's question. "
                    "Return the SQL query and nothing else — no explanation, no markdown, no backticks."
                )
            },
            {"role": "user", "content": query}
        ],
        "max_tokens": 300,
        "temperature": 0,
        "top_p": 0.1
    }).encode()

    sql_req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=sql_payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
    )

    try:
        with urllib.request.urlopen(sql_req) as res:
            sql_result = json.loads(res.read())
            generated_sql = clean_sql(sql_result["choices"][0]["message"]["content"])
            print(f"DEBUG: Generated SQL → {generated_sql}")
    except Exception as e:
        return f"Failed to generate SQL: {str(e)}"

    # step 2 — execute SQL
    result = run_query(generated_sql)

    if not result["success"]:
        return f"SQL execution failed: {result['error']}\nGenerated SQL: {generated_sql}"

    # step 3 — explain results
    results_text = f"SQL query: {generated_sql}\n"
    results_text += f"Columns: {result['columns']}\n"
    results_text += f"Results ({result['total']} rows):\n"
    for row in result["rows"][:10]:
        results_text += f"  {row}\n"

    explain_payload = json.dumps({
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": (
                    PERSONA +
                    "Explain the SQL query results below in plain English. "
                    "Be direct and specific, and report the numbers exactly as given. "
                    "Never change, round or invent data. "
                    "Greet the user only if their question was a greeting. "
                    "No code snippets."
                )
            },
            {
                "role": "user",
                "content": f"Original question: {query}\n\n{results_text}"
            }
        ],
        "max_tokens": 500,
        "temperature": 0,
        "top_p": 0.1
    }).encode()

    explain_req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=explain_payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
    )

    try:
        with urllib.request.urlopen(explain_req) as res:
            explain_result = json.loads(res.read())
            return explain_result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Results:\n{results_text}\n(Explanation failed: {str(e)})"

def load_schema_from_terminal():
    """Load schema from terminal input or restore from last saved session."""
    print("\n==================================================")
    print("   Analytics Agent — Schema Insights")
    print("==================================================")

    saved = load_schema()
    if saved:
        print(f"\nFound saved schema from {saved['loaded_at']}")
        print("  Tables:", list(saved["schema"].keys()))
        choice = input("\nUse saved schema? (y/n): ").strip().lower()
        if choice == "y":
            state.update(saved)
            print("\n--- Schema Restored ---")
            for table, columns in state["schema"].items():
                print(f"  Table: {table} ({len(columns)} columns)")
            if state["total_rows"]:
                print(f"  Rows: {state['total_rows']} | Columns: {state['total_cols']}")
            print(f"\nSession ID: {state['session_id']}")
            webbrowser.open(f"file:///{file_path}")
            print("Users can now ask questions about the schema.\n")
            return
        else:
            clear_schema()

    print("\nHow would you like to provide your schema?")
    print("  1 → Paste SQL directly")
    print("  2 → Load from .sql file")
    print("  3 → Load from .csv file")
    choice = input("\nChoice (1/2/3): ").strip()

    schema, sample_rows = {}, []
    total_rows, total_cols = 0, 0

    if choice == "1":
        print("\nPaste your SQL below. Type END on a new line when done:\n")
        lines = []
        while True:
            line = input()
            if line.strip().upper() == "END":
                break
            lines.append(line)
        schema = parse_sql('\n'.join(lines))

    elif choice == "2":
        path = input("\nEnter file path: ").strip().strip('"')
        if not os.path.exists(path):
            print("File not found.")
            return
        with open(path, 'r') as f:
            schema = parse_sql(f.read())

    elif choice == "3":
        path = input("\nEnter CSV file path: ").strip().strip('"')
        if not os.path.exists(path):
            print("File not found.")
            return
        schema, sample_rows = load_csv(path)
        table_name = load_csv_to_sqlite(
            path,
            path.replace("\\", "/").split("/")[-1].replace(".csv", "")
        )
        state["table_name"] = table_name
        print(f"  Loaded into SQLite as table: {table_name}")
        with open(path, 'r', encoding='utf-8-sig') as f:
            all_lines = f.readlines()
        total_rows = len(all_lines) - 1
        total_cols = len(all_lines[0].split(',')) if all_lines else 0

    if not schema:
        print("No schema loaded.")
        return

    masked = mask_schema(schema)
    joins = detect_joins(schema)
    schema_str = str(masked)
    session_id = generate_session_id(schema_str)

    state["schema"] = schema
    state["masked"] = masked
    state["joins"] = joins
    state["sample_rows"] = sample_rows
    state["schema_str"] = schema_str
    state["session_id"] = session_id
    state["total_rows"] = total_rows
    state["total_cols"] = total_cols

    save_schema(state)

    print("\n--- Schema Loaded ---")
    for table, columns in schema.items():
        print(f"  Table: {table} ({len(columns)} columns)")
    if total_rows:
        print(f"  Rows: {total_rows} | Columns: {total_cols}")
    if joins:
        print("\n--- Relationships ---")
        for j in joins:
            print(f"  {j['from_table']}.{j['from_col']} → {j['to_table']}.{j['to_col']}")

    print(f"\nSession ID: {session_id}")
    webbrowser.open(f"file:///{file_path}")
    print("Users can now ask questions about the schema.\n")

def build_schema_context() -> str:
    """Build schema context string to inject into GPT system prompt."""
    if not state["masked"]:
        return ""
    lines = ["SCHEMA:"]
    for table, columns in state["masked"].items():
        lines.append(f"\nTable: {table}")
        for col, dtype in columns.items():
            lines.append(f"  - {col}: {dtype}")
    if state["joins"]:
        lines.append("\nRELATIONSHIPS:")
        for j in state["joins"]:
            lines.append(f"  - {j['from_table']}.{j['from_col']} → {j['to_table']}.{j['to_col']}")
    if state["total_rows"]:
        lines.append("\nDATASET INFO:")
        lines.append(f"  - Total rows: {state['total_rows']}")
        lines.append(f"  - Total columns: {state['total_cols']}")
    if state["sample_rows"]:
        lines.append("\nSAMPLE DATA (first 3 rows):")
        for i, row in enumerate(state["sample_rows"][:3], 1):
            lines.append(f"  Row {i}: {row}")
    return '\n'.join(lines)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Suppress default HTTP request logging."""
        pass

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        """Handle incoming chat requests from the browser UI."""
        if self.path != "/chat":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        messages = body.get("messages", [])
        query = messages[-1]["content"] if messages else ""

        session_id = state["session_id"]
        schema = state["schema"]
        schema_str = state["schema_str"]

        # check cache
        cached = get_cached(schema_str, query)
        if cached and not should_bypass_cache(query):
            save_message(session_id, "user", query, extract_keywords(query))
            save_message(session_id, "assistant", cached)
            self._respond({"reply": cached, "cached": True})
            return

        # retrieve memory context
        relevant = retrieve_relevant(session_id, query)
        summaries = get_summaries(session_id)

        memory_context = ""
        if summaries:
            memory_context += "PAST SESSION SUMMARIES:\n"
            for s in summaries:
                memory_context += f"- {s['summary']}\n"
        if relevant:
            memory_context += "\nRELEVANT PAST EXCHANGES:\n"
            for r in relevant:
                memory_context += f"- {r['content']}\n"

        # guard
        validated_query = validate_query(query, schema)
        if memory_context:
            validated_query += f"\n\nMEMORY CONTEXT:\n{memory_context}"

        schema_context = build_schema_context()
        system = (
            PERSONA +
            "Greet the user only when they greet you first, and make them feel heard. "
            "Answer in the context of the schema and sample data below, "
            "with specific, actionable insights. "
            "Never invent tables or columns that are not in the schema. "
            "Flag anomalies, suggest optimisations, and explain relationships clearly.\n\n"
            + schema_context
        )

        try:
            if state["table_name"] and needs_sql(query):
                print(f"DEBUG: SQL path → table={state['table_name']}")
                reply = generate_and_run_sql(validated_query, schema_context, state["table_name"])
            else:
                print(f"DEBUG: Direct path → table='{state['table_name']}' needs_sql={needs_sql(query)}")
                recent = get_recent_messages(session_id, limit=6)
                api_messages = recent + [{"role": "user", "content": validated_query}]

                payload = json.dumps({
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "system", "content": system}] + api_messages,
                    "max_tokens": 1000,
                    "temperature": 0,
                    "top_p": 0.1
                }).encode()

                req = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {API_KEY}"
                    }
                )

                with urllib.request.urlopen(req) as res:
                    result = json.loads(res.read())
                    reply = result["choices"][0]["message"]["content"]

            save_to_cache(schema_str, query, reply)
            save_message(session_id, "user", query, extract_keywords(query))
            save_message(session_id, "assistant", reply)

            if should_summarise(session_id):
                threading.Thread(target=summarise_session, args=(session_id,)).start()

            self._respond({"reply": reply})

        except urllib.error.HTTPError as e:
            error = e.read().decode()
            self._respond({"error": error}, status=500)

    def _respond(self, data: dict, status: int = 200):
        """Send JSON response with CORS headers."""
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _cors(self):
        """Add CORS headers to allow browser requests."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

if __name__ == "__main__":
    load_schema_from_terminal()
    HTTPServer(("localhost", 8000), Handler).serve_forever()