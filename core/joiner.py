# ↑ FK detection, table linking

def detect_joins(schema: dict) -> list:
    """Detect potential foreign-key relationships between tables using column names."""
    joins = []
    table_names = list(schema.keys())

    for table, columns in schema.items():
        for col in columns:
            # look for columns ending in _id
            if col.endswith('_id'):
                # guess the referenced table from the prefix
                # e.g. user_id → users, order_id → orders
                prefix = col[:-3]  # strip '_id'
                for other_table in table_names:
                    if other_table.lower().startswith(prefix.lower()):
                        joins.append({
                            "from_table": table,
                            "from_col": col,
                            "to_table": other_table,
                            "to_col": "id"
                        })
    return joins