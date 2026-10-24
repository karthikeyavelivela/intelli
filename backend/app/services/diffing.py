import difflib
import re

TRACKED = [
    "name", "description", "business_definition", "formula", "filters", "aggregation", "unit",
    "time_window", "date_column", "dataset_id", "department", "category",
]


def diff_snapshots(a: dict, b: dict) -> list[dict]:
    out = []
    for f in TRACKED:
        if (a.get(f) or None) != (b.get(f) or None):
            out.append({"field": f, "from": a.get(f), "to": b.get(f)})
    return out


def token_diff(a: str | None, b: str | None) -> list[dict]:
    """Token-level diff for side-by-side rendering. Segments: {op: equal|replace|delete|insert, a, b}."""
    ta = re.findall(r"\w+|\s+|[^\w\s]", a or "")
    tb = re.findall(r"\w+|\s+|[^\w\s]", b or "")
    sm = difflib.SequenceMatcher(a=ta, b=tb, autojunk=False)
    return [{"op": op, "a": "".join(ta[i1:i2]), "b": "".join(tb[j1:j2])} for op, i1, i2, j1, j2 in sm.get_opcodes()]
