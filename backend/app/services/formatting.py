"""Shared backend number/date formatting (reports, exports, TARA answers). Indian conventions:
lakh/crore digit grouping (12,45,300), rupee symbol, DD-MMM-YYYY dates in IST."""
from __future__ import annotations

from .calendar_in import fmt_date, fmt_datetime_ist  # re-exported for callers

RUPEE = "₹"


def group_indian(int_digits: str) -> str:
    """'1245300' -> '12,45,300'"""
    if len(int_digits) <= 3:
        return int_digits
    head, tail = int_digits[:-3], int_digits[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


def number_en_in(v: float, decimals: int = 2) -> str:
    neg = v < 0
    s = f"{abs(v):.{decimals}f}"
    whole, _, frac = s.partition(".")
    out = group_indian(whole) + (f".{frac}" if frac else "")
    return f"-{out}" if neg else out


def inr(v: float | int | None, decimals: int | None = None) -> str:
    """Rupee amount in en-IN grouping. Default: no decimals from 1,000 up, 2 decimals below."""
    if v is None:
        return "n/a"
    v = float(v)
    d = decimals if decimals is not None else (0 if abs(v) >= 1000 else 2)
    n = number_en_in(abs(v), d)
    return f"-{RUPEE}{n}" if v < 0 else f"{RUPEE}{n}"


def compact_in(v: float | int | None, currency: bool = False) -> str:
    """1,20,00,000 -> '1.2 Cr', 4,50,000 -> '4.5 L', 12,500 -> '12.5 K'"""
    if v is None:
        return "n/a"
    v = float(v)
    a = abs(v)
    for div, suffix in ((1e7, " Cr"), (1e5, " L"), (1e3, " K")):
        if a >= div:
            n = f"{a / div:.2f}".rstrip("0").rstrip(".")
            return f"{'-' if v < 0 else ''}{RUPEE if currency else ''}{n}{suffix}"
    return f"{'-' if v < 0 else ''}{RUPEE if currency else ''}{number_en_in(a, 0 if a == int(a) else 2)}"


def format_value(v, unit: str | None) -> str:
    if v is None:
        return "n/a"
    u = (unit or "").lower()
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if u in ("inr", RUPEE, "rs", "currency"):
        return inr(f)
    if u in ("usd", "$"):
        return f"${number_en_in(f, 0 if abs(f) >= 1000 else 2)}"
    if u in ("percent", "%", "pct"):
        return f"{number_en_in(f, 1)}%"
    if f == int(f) and abs(f) < 1e15:
        return number_en_in(f, 0)
    return number_en_in(f, 2)
