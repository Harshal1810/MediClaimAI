from __future__ import annotations

from datetime import date, datetime


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value.strip()
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def days_between(start: date, end: date) -> int:
    return (end - start).days

