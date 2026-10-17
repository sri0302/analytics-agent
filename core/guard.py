# ↑ hallucination pre-flight check

import re

def extract_words(text: str) -> set:
    """Extract unique lowercase words from the given text."""
    return set(re.findall(r'\b\w+\b', text.lower()))

def validate_query(query: str, schema: dict) -> str:
    """Check for unknown schema terms and append a guard note if found."""
    known = set()
    for table, columns in schema.items():
        known.add(table.lower())
        for col in columns:
            known.add(col.lower())

    query_words = extract_words(query)

    # find words in query that look like table/column names
    # but don't exist in schema
    suspicious = []
    for word in query_words:
        if len(word) > 3:  # ignore short words like 'the', 'for'
            if '_' in word or word in known:
                if word not in known:
                    suspicious.append(word)

    if suspicious:
        known_list = ', '.join(sorted(known))
        note = (
            f"\n[GUARD NOTE] The following terms in the query don't match "
            f"the schema: {', '.join(suspicious)}. "
            f"Only use these known tables/columns: {known_list}"
        )
        return query + note

    return query