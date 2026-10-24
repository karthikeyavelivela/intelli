"""Indian business calendar helpers: IST clock, financial year (1 April - 31 March), fiscal quarters and festival windows.

Fiscal quarters:  Q1 = Apr-Jun, Q2 = Jul-Sep, Q3 = Oct-Dec, Q4 = Jan-Mar.
A financial year is identified by its START year: FY 2025-26 starts 01-Apr-2025 and has start_year 2025.
"""
from __future__ import annotations

import calendar
import datetime as dt
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
FQ_START_MONTH = {1: 4, 2: 7, 3: 10, 4: 1}


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


def today_ist() -> dt.date:
    return now_ist().date()


def fmt_date(d: dt.date | dt.datetime | str | None) -> str:
    """DD-MMM-YYYY"""
    if d is None or d == "":
        return "-"
    if isinstance(d, str):
        d = dt.date.fromisoformat(d[:10])
    return d.strftime("%d-%b-%Y")


def to_ist(naive_utc: dt.datetime) -> dt.datetime:
    """Database timestamps are naive UTC; convert for display."""
    return naive_utc.replace(tzinfo=dt.timezone.utc).astimezone(IST)


def fmt_datetime_ist(naive_utc: dt.datetime | None) -> str:
    return "-" if naive_utc is None else to_ist(naive_utc).strftime("%d-%b-%Y %H:%M IST")


def fy_start_year(d: dt.date) -> int:
    return d.year if d.month >= 4 else d.year - 1


def fy_label(start_year: int) -> str:
    return f"FY {start_year}-{str(start_year + 1)[2:]}"


def fy_bounds(start_year: int) -> tuple[dt.date, dt.date]:
    return dt.date(start_year, 4, 1), dt.date(start_year + 1, 3, 31)


def fq_of(d: dt.date) -> tuple[int, int]:
    """(fy_start_year, quarter 1-4)"""
    return fy_start_year(d), ((d.month - 4) % 12) // 3 + 1


def fq_bounds(start_year: int, q: int) -> tuple[dt.date, dt.date]:
    m = FQ_START_MONTH[q]
    y = start_year if m >= 4 else start_year + 1
    end_m = m + 2
    return dt.date(y, m, 1), dt.date(y, end_m, calendar.monthrange(y, end_m)[1])


def fq_label(start_year: int, q: int) -> str:
    return f"Q{q} {fy_label(start_year)}"


def prev_fq(start_year: int, q: int) -> tuple[int, int]:
    return (start_year, q - 1) if q > 1 else (start_year - 1, 4)


def last_completed_fq(today: dt.date) -> tuple[int, int]:
    return prev_fq(*fq_of(today))


# ----------------------------------------------------------------------------- festivals (synthetic-data calendar)
FESTIVAL_DATES: dict[str, dict[int, dt.date]] = {
    "diwali": {2023: dt.date(2023, 11, 12), 2024: dt.date(2024, 11, 1), 2025: dt.date(2025, 10, 20), 2026: dt.date(2026, 11, 8), 2027: dt.date(2027, 10, 29)},
    "dussehra": {2023: dt.date(2023, 10, 24), 2024: dt.date(2024, 10, 12), 2025: dt.date(2025, 10, 2), 2026: dt.date(2026, 10, 20), 2027: dt.date(2027, 10, 9)},
    "holi": {2024: dt.date(2024, 3, 25), 2025: dt.date(2025, 3, 14), 2026: dt.date(2026, 3, 4), 2027: dt.date(2027, 3, 22)},
    "eid": {2024: dt.date(2024, 4, 11), 2025: dt.date(2025, 3, 31), 2026: dt.date(2026, 3, 20), 2027: dt.date(2027, 3, 10)},
}
# (days before, days after) the festival date that make up its sales "season"
FESTIVAL_SPAN = {"diwali": (14, 5), "dussehra": (9, 1), "holi": (7, 2), "eid": (7, 3)}
FESTIVAL_LABEL = {"diwali": "Diwali season", "dussehra": "Dussehra season", "holi": "Holi season", "eid": "Eid season", "sankranti": "Pongal/Sankranti season", "eoss": "End-of-Season sale"}


def festival_windows(name: str, years: range) -> list[tuple[dt.date, dt.date]]:
    out: list[tuple[dt.date, dt.date]] = []
    for y in years:
        if name in FESTIVAL_DATES:
            d = FESTIVAL_DATES[name].get(y)
            if d:
                b, a = FESTIVAL_SPAN[name]
                out.append((d - dt.timedelta(days=b), d + dt.timedelta(days=a)))
        elif name == "sankranti":
            out.append((dt.date(y, 1, 8), dt.date(y, 1, 18)))
        elif name == "eoss":
            out += [(dt.date(y, 1, 10), dt.date(y, 1, 31)), (dt.date(y, 6, 25), dt.date(y, 7, 15))]
    return sorted(out)


def latest_festival_window(name: str, today: dt.date) -> tuple[dt.date, dt.date] | None:
    """Most recent season that has already started."""
    wins = [w for w in festival_windows(name, range(today.year - 3, today.year + 1)) if w[0] <= today]
    if not wins:
        return None
    s, e = wins[-1]
    return s, min(e, today)
