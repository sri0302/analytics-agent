# analytics-agent

A terminal + browser tool for AI-assisted database analysis. You load a schema from the terminal, users ask questions about it from a chat UI.

Built as a learning project — I wanted to understand how to wire together a real AI pipeline from scratch rather than just wrapping an API call.

![Python](https://img.shields.io/badge/python-3.10+-blue) ![OpenAI](https://img.shields.io/badge/OpenAI-gpt--4o--mini-green) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## what it does

- parses SQL `CREATE TABLE` statements or CSV files into a schema
- detects foreign key relationships from naming conventions (`user_id` → `users.id`)
- masks PII columns (`email`, `name`, `phone`, etc) before anything touches the API
- validates queries against the schema before sending — catches hallucinated column names
- caches responses in SQLite so identical queries never hit the API twice
- stores full conversation history in a data pool with keyword + embedding retrieval
- compresses older messages into summaries every 10 turns
- serves a minimal dark-themed chat UI over a local HTTP server

---

## stack

- Python 3.10+
- OpenAI API (gpt-4o-mini)
- SQLite (via stdlib `sqlite3`) — cache + data pool
- `python-dotenv` — env management
- vanilla HTML/JS — frontend

no frameworks, no heavy dependencies. wanted to keep it readable.

---

## setup

```bash
git clone https://github.com/sri0302/analytics-agent.git
cd analytics-agent

python -m venv venv
venv\Scripts\activate       # windows
# source venv/bin/activate  # mac/linux

pip install openai python-dotenv numpy
```

create a `.env` file:
```
OPENAI_API_KEY=your_key_here
```

---

## usage

**terminal (operator loads the schema):**
```bash
python server.py
```

picks up your schema via:
- paste SQL directly
- load a `.sql` file
- load a `.csv` file (type inference included)

once the schema is loaded, the server starts on `localhost:8000`.

**browser (end user asks questions):**

open `index.html` in your browser and start asking. the schema context is injected automatically — users never see it.

---

## project structure

```
analytics-agent/
├── ingestion/
│   ├── parser.py        # SQL CREATE TABLE → dict
│   └── csv_loader.py    # CSV → schema + sample rows
├── core/
│   ├── masker.py        # PII detection + flagging
│   ├── joiner.py        # FK relationship detection
│   ├── cache.py         # SQLite response cache
│   ├── guard.py         # pre-flight hallucination check
│   ├── datapool.py      # full conversation store
│   ├── retriever.py     # keyword + embedding search
│   └── summariser.py    # session compression
├── ai/
│   └── openai.py        # GPT integration
├── server.py            # HTTP server + schema loader
├── index.html           # chat UI
└── config.py            # env loader
```

---

## things i figured out building this

the hallucination guard was the most interesting part — LLMs confidently make up column names that don't exist. injecting a correction note before the API call (rather than after) cuts that down significantly.

the data pool architecture came from wanting full conversation memory without dumping the entire history into every API call. keyword search handles most retrieval, embeddings kick in when keyword overlap is weak.

PII masking happens at the schema level — the actual column structure is preserved so the AI understands the tables, but sensitive field names get flagged so the model knows not to treat them as queryable.

---

## known limitations

- embedding search requires the OpenAI embeddings endpoint (adds cost per query)
- no auth on the HTTP server — local use only
- CSV type inference is basic (INT / FLOAT / VARCHAR)
- single schema per session

---


