# ↑ SQL/JSON schema parser

import re

def parse_sql(sql_text: str) -> dict:
    """Parse SQL CREATE TABLE statements into a nested dictionary."""
    ...

def parse_sql(sql_text: str) -> dict:
    schema = {}
    tables = re.findall(
        r'CREATE\s+TABLE\s+(\w+)\s*\((.*?)\);',
        sql_text,
        re.IGNORECASE | re.DOTALL
    )
    for table_name, columns_block in tables:
        columns = {}
        for line in columns_block.strip().split('\n'):
            line = line.strip().rstrip(',')
            if not line:
                continue
            if any(line.upper().startswith(k) for k in ['PRIMARY', 'FOREIGN', 'UNIQUE', 'INDEX', 'KEY', 'CONSTRAINT']):
                continue
            parts = line.split()
            if len(parts) >= 2:
                col_name = parts[0]
                col_type = parts[1]
                columns[col_name] = col_type
        schema[table_name] = columns
    return schema