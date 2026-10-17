from openai import OpenAI
import config

client = OpenAI(api_key=config.OPENAI_API_KEY)

def build_context(masked_schema: dict, joins: list) -> str:
    lines = ["SCHEMA:"]
    for table, columns in masked_schema.items():
        lines.append(f"\nTable: {table}")
        for col, dtype in columns.items():
            lines.append(f"  - {col}: {dtype}")

    if joins:
        lines.append("\nRELATIONSHIPS:")
        for j in joins:
            lines.append(
                f"  - {j['from_table']}.{j['from_col']} → {j['to_table']}.{j['to_col']}"
            )
    return '\n'.join(lines)

def get_insight(masked_schema: dict, joins: list, query: str, sample_rows: list = [], history: list = []) -> str:
    context = build_context(masked_schema, joins)

    if sample_rows:
        context += "\n\nSAMPLE DATA (first 3 rows, PII masked):\n"
        for i, row in enumerate(sample_rows, 1):
            context += f"  Row {i}: {row}\n"

    system_message = {
        "role": "system",
        "content": (
            "You are a database analyst. Analyse the schema and sample data "
            "provided and answer the user's question with specific, actionable insights. "
            "Never invent tables or columns not present in the schema. "
            "Flag anomalies, suggest optimizations, and explain relationships clearly. "
            f"Here is the schema context:\n{context}"
        )
    }

    messages = [system_message] + history + [{"role": "user", "content": query}]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=1000
    )
    return response.choices[0].message.content