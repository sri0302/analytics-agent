import json
import numpy as np
from core.datapool import get_all_messages

def extract_keywords(text: str) -> list:
    """Extract meaningful keywords by removing common stopwords."""
    import re
    # remove common words, keep meaningful terms
    stopwords = {
        'what', 'is', 'the', 'a', 'an', 'are', 'in', 'of', 'to',
        'and', 'for', 'this', 'that', 'it', 'do', 'how', 'why',
        'can', 'you', 'me', 'my', 'i', 'about', 'any', 'with',
        'tell', 'show', 'give', 'get', 'has', 'have', 'which'
    }
    words = re.findall(r'\b\w+\b', text.lower())
    return [w for w in words if w not in stopwords and len(w) > 2]

def keyword_search(session_id: str, query: str, top_k: int = 3) -> list:
    """Retrieve user messages ranked by keyword overlap with the query."""
    query_keywords = set(extract_keywords(query))
    all_messages = get_all_messages(session_id)
    scored = []

    for msg in all_messages:
        if msg['role'] != 'user':
            continue
        msg_keywords = set(msg['keywords']) if msg['keywords'] else set(extract_keywords(msg['content']))
        overlap = len(query_keywords & msg_keywords)
        if overlap > 0:
            scored.append((overlap, msg))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:top_k]]

def cosine_similarity(a: list, b: list) -> float:
    """Calculate cosine similarity between two vectors."""
    a, b = np.array(a), np.array(b)
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def embedding_search(session_id: str, query_embedding: list, top_k: int = 3) -> list:
    """Retrieve user messages whose embeddings exceed the similarity threshold."""
    all_messages = get_all_messages(session_id)
    scored = []

    for msg in all_messages:
        if not msg['embedding'] or msg['role'] != 'user':
            continue
        score = cosine_similarity(query_embedding, msg['embedding'])
        if score > 0.7:  # similarity threshold
            scored.append((score, msg))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:top_k]]

def retrieve_relevant(session_id: str, query: str, query_embedding: list = []) -> list:
    """Combine keyword and embedding search results, removing duplicate messages."""
    # step 1 - keyword search
    keyword_results = keyword_search(session_id, query)

    # step 2 - embedding fallback if weak keyword match
    embedding_results = []
    if len(keyword_results) < 2 and query_embedding:
        embedding_results = embedding_search(session_id, query_embedding)

    # merge and deduplicate by content
    seen = set()
    combined = []
    for msg in keyword_results + embedding_results:
        if msg['content'] not in seen:
            seen.add(msg['content'])
            combined.append(msg)

    return combined