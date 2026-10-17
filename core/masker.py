# ↑ PII detection + hashing

import hashlib

# columns that are considered PII
PII_PATTERNS = [
    'email', 'phone', 'mobile', 'name', 'address',
    'ssn', 'dob', 'birth', 'gender', 'ip', 'location',
    'zip', 'postal', 'passport', 'license', 'salary'
]

def is_pii(column_name: str) -> bool:
    """Check whether a column name matches common PII patterns."""
    col = column_name.lower()
    return any(pattern in col for pattern in PII_PATTERNS)

def mask_value(value: str) -> str:
    """Hash a value with SHA-256 and return the first 12 hexadecimal characters."""
    return hashlib.sha256(value.encode()).hexdigest()[:12]

def mask_schema(schema: dict) -> dict:
    """Mark PII columns as masked in a copy of the schema."""
    masked = {}
    for table, columns in schema.items():
        masked[table] = {}
        for col, dtype in columns.items():
            if is_pii(col):
                masked[table][col] = f"{dtype} [MASKED]"
            else:
                masked[table][col] = dtype
    return masked