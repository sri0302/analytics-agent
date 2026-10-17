# Analytics Agent — Build Log

A full record of every module built, why it exists, and what went wrong along the way.

---

## 1. Environment Setup

**What:** Isolated Python environment for the project.

**Why:** Virtual environments keep dependencies separate from your global Python install. Prevents version conflicts across projects.

**How:**
```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install openai python-dotenv
```

**Result:** `(venv)` in terminal. All packages install to `Analytics Agent/venv/` not globally.

---

## 2. API Key Management (.env + config.py)

**What:** Stored the OpenAI API key outside of source code.

**Why:** Hardcoding secrets into code means anyone who sees your code sees your key. `.env` keeps secrets separate and out of Git.

**How:**
- `.env` holds the raw key: `OPENAI_API_KEY=sk-...`
- `config.py` loads it at runtime using `python-dotenv`

```python
from dotenv import load_dotenv
import os
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
```

**Result:** Any module can `import config` and use `config.OPENAI_API_KEY` safely.

---

## 3. API Connection Test (test_connection.py)

**What:** Verified the OpenAI API is reachable and the key works.

**Why:** Always test the outermost dependency first. If the API doesn't work, nothing else matters.

**Errors encountered & fixed:**
- `UnicodeDecodeError` → `.env` saved as UTF-16, recreated as UTF-8
- `RateLimitError 429` → no billing on OpenAI account, added credit

**Result:** API responded. Stack confirmed working end-to-end.

---

## 4. Schema Parser (ingestion/parser.py)

**What:** Parses raw SQL `CREATE TABLE` statements into a Python dictionary.

**Why:** Every downstream module needs the schema in a consistent format. Parse once, share everywhere.

**How:** Uses Python's built-in `re` module — no extra packages.

```python
import re

def parse_sql(sql_text: str) -> dict:
    schema = {}
    tables = re.findall(
        r'CREATE\s+TABLE\s+(\w+)\s*\((.*?)\);',
        sql_text, re.IGNORECASE | re.DOTALL
    )
    for table_name, columns_block in tables:
        columns = {}
        for line in columns_block.strip().split('\n'):
            line = line.strip().rstrip(',')
            if not line:
                continue
            if any(line.upper().startswith(k) for k in
                   ['PRIMARY', 'FOREIGN', 'UNIQUE', 'INDEX', 'KEY', 'CONSTRAINT']):
                continue
            parts = line.split()
            if len(parts) >= 2:
                columns[parts[0]] = parts[1]
        schema[table_name] = columns
    return schema
```

**Output format:**
```python
{
  "users":  {"id": "INT", "email": "VARCHAR", "name": "VARCHAR"},
  "orders": {"id": "INT", "user_id": "INT", "total": "DECIMAL"}
}
```

**Errors encountered & fixed:**
- `circular import` → `parser.py` accidentally imported itself, removed the self-import line
- Missing `__init__.py` → needed in `ingestion/` for Python to treat it as a module

---

## 5. CSV Loader (ingestion/csv_loader.py)

**What:** Loads a CSV file, infers column types, returns a schema dict + sample rows.

**Why:** Not all schemas come as SQL. CSV files are common and need type inference since they don't declare types explicitly.

**How:** Reads headers, tries to cast each column's values as INT → FLOAT → VARCHAR. Returns the first 3 rows as sample data for the AI context.

**Note:** Uses `utf-8-sig` encoding to handle Excel-saved CSVs which add a hidden BOM character.

---

## 6. PII Masker (core/masker.py)

**What:** Scans schema column names and flags any containing sensitive personal data.

**Why:** End user data is confidential. Masking at the schema level ensures nothing sensitive leaks into API calls.

**How:** Checks column names against PII keywords (`email`, `phone`, `name`, `ssn`, `dob`, etc). Appends `[MASKED]` to flagged column types. For actual values, uses `sha256` hashing — same value always produces the same 12-char fingerprint, consistent across joined tables but unreadable.

**Output:**
```
name  → VARCHAR(100) [MASKED]
email → VARCHAR(100) [MASKED]
id    → INT
```

---

## 7. Join Detector (core/joiner.py)

**What:** Automatically detects foreign key relationships between tables.

**Why:** The AI needs to understand how tables relate. Inferring from naming conventions means no manual config.

**How:** Scans every column for the `_id` suffix. Strips it to get a prefix (`user_id` → `user`), then finds a table starting with that prefix (`users`). Records the join.

**Output:**
```python
{"from_table": "orders", "from_col": "user_id", "to_table": "users", "to_col": "id"}
```

---

## 8. Memory Cache (core/cache.py)

**What:** Stores AI responses in SQLite so identical queries never hit the API twice.

**Why:** Saves tokens and cost. Makes repeated queries instant. Persists across sessions.

**How:** Hashes schema + query together with MD5 as a cache key. Checks SQLite on every request. Hit = instant return. Miss = API call + auto-save.

---

## 9. Hallucination Guard (core/guard.py)

**What:** Validates the user's query against the actual schema before the API call.

**Why:** LLMs confidently invent column names that don't exist. Catching this before the call keeps the AI grounded.

**How:** Extracts words from the query, flags any that look like schema identifiers but don't exist in the parsed schema. Appends a `[GUARD NOTE]` listing only valid tables and columns.

---

## 10. AI Insights Engine (ai/openai.py)

**What:** Sends masked schema, join map, and validated query to GPT. Returns insights.

**Why:** This is the brain — everything else feeds into this call.

**How:** `build_context()` formats schema and joins into readable text. `get_insight()` sends it to `gpt-4o-mini` with a system prompt that instructs it to never invent schema elements.

**Double hallucination protection:**
- Guard injects schema correction into the query
- System prompt tells GPT to never invent tables or columns

---

## 11. Data Pool (core/datapool.py)

**What:** Persistent SQLite store for every conversation message across sessions.

**Why:** Full memory without dumping entire history into every API call. Store everything, retrieve only what's relevant.

**How:** Two tables — `conversations` stores every message with keywords and embedding vectors. `summaries` stores compressed session overviews. Session ID is generated from the schema hash so each schema gets its own history.

---

## 12. Retriever (core/retriever.py)

**What:** Finds relevant past messages for a given query.

**Why:** Instead of sending all history on every call, pull only what's actually relevant to the current question.

**How:** Two-stage retrieval:
1. Keyword search — fast, free, no API cost
2. Embedding similarity — cosine distance via numpy, kicks in when keyword match is weak (< 2 hits)

Deduplicates results across both methods before returning.

---

## 13. Summariser (core/summariser.py)

**What:** Compresses older conversation turns into bullet point summaries.

**Why:** Long sessions accumulate a lot of messages. Summaries give the agent "long-term memory" of the big picture without growing the context window indefinitely.

**How:** Every 10 messages, sends the full session to GPT and asks for a 3-5 bullet summary. Saved to the `summaries` table. Runs in a background thread so it doesn't block the response.

---

## 14. HTTP Server (server.py)

**What:** A combined schema loader + HTTP server that proxies browser requests to OpenAI.

**Why:** Browsers can't call the OpenAI API directly (CORS). The server acts as a middleman — keeps the API key server-side, injects schema context automatically, runs the full pipeline on every request.

**How:** Operator loads the schema via terminal on startup. Schema gets stored in a shared `state` dict. Every browser POST to `/chat` gets the schema injected into the system prompt, runs through cache → guard → retriever → summariser → OpenAI → response.

---

## 15. Chat UI (index.html)

**What:** Minimal dark-themed browser chat interface.

**Why:** End users shouldn't need a terminal. Simple input → response is all they need.

**How:** Vanilla HTML/JS. Sends conversation history on every request to maintain context. Typing indicator, auto-resizing input, keyboard shortcuts.

---

## 16. GitHub + README

**What:** Pushed the project to GitHub with a clean README.

**Errors encountered & fixed:**
- `.env` committed in first commit → rotated API key, wiped git history, force pushed
- GitHub push protection blocked push due to secret in history → nuked `.git`, reinitialised

---

## Final Project Structure

```
Analytics Agent/
├── venv/                    ← isolated environment
├── ingestion/
│   ├── __init__.py
│   ├── parser.py            ← SQL schema parser
│   └── csv_loader.py        ← CSV ingestion + type inference
├── core/
│   ├── __init__.py
│   ├── masker.py            ← PII detection + flagging
│   ├── joiner.py            ← FK relationship detection
│   ├── cache.py             ← SQLite response cache
│   ├── guard.py             ← hallucination prevention
│   ├── datapool.py          ← full conversation store
│   ├── retriever.py         ← keyword + embedding search
│   └── summariser.py        ← session compression
├── ai/
│   ├── __init__.py
│   └── openai.py            ← GPT insights engine
├── server.py                ← HTTP server + schema loader (entry point)
├── index.html               ← chat UI
├── config.py                ← env loader
├── .env                     ← secret keys, never commit
├── .gitignore
└── README.md
```

---

## Key decisions made

- **No sliding window** — full history stored in data pool, retrieval handles relevance
- **Operator/user separation** — schema loaded via terminal, users only see the chat UI
- **Double hallucination guard** — pre-flight schema validation + system prompt constraints
- **SQLite over external DB** — zero dependencies, single file, built into Python
- **gpt-4o-mini** — cheap enough to run thousands of calls on a few dollars, sufficient for schema analysis
- **No file upload in UI** — operator controls what data the agent sees
