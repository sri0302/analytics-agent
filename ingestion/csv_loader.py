import csv
from collections import defaultdict

def infer_type(sql_text: str) -> dict:
    """Parse SQL CREATE TABLE statements into a nested dictionary."""
    ...

def infer_type(values: list) -> str:
    types = set()
    for v in values:
        v = v.strip()
        if not v:
            continue
        try:
            int(v)
            types.add("INT")
            continue
        except ValueError:
            pass
        try:
            float(v)
            types.add("FLOAT")
            continue
        except ValueError:
            pass
        types.add("VARCHAR")

    if "VARCHAR" in types:
        return "VARCHAR"
    if "FLOAT" in types:
        return "FLOAT"
    return "INT"

def load_csv(path: str) -> tuple[dict, list[dict]]:
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader]

    if not rows:
        return {}, []

    # infer schema from columns
    table_name = path.replace("\\", "/").split("/")[-1].replace(".csv", "").lower()
    columns_data = defaultdict(list)

    for row in rows:
        for col, val in row.items():
            columns_data[col.strip()].append(val)

    schema = {
        table_name: {
            col: infer_type(vals)
            for col, vals in columns_data.items()
        }
    }

    # return first 3 rows as sample
    sample_rows = rows[:3]

    return schema, sample_rows