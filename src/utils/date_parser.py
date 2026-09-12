import re
from datetime import date, datetime, timedelta
from typing import Optional

_UNIT_ALIASES = {
    "s": "seconds",
    "sec": "seconds",
    "secs": "seconds",
    "second": "seconds",
    "seconds": "seconds",
    "m": "minutes",
    "min": "minutes",
    "mins": "minutes",
    "minute": "minutes",
    "minutes": "minutes",
    "h": "hours",
    "hr": "hours",
    "hrs": "hours",
    "hour": "hours",
    "hours": "hours",
    "d": "days",
    "day": "days",
    "days": "days",
    "w": "weeks",
    "wk": "weeks",
    "wks": "weeks",
    "week": "weeks",
    "weeks": "weeks",
    "mo": "months",
    "mos": "months",
    "month": "months",
    "months": "months",
    "y": "years",
    "yr": "years",
    "yrs": "years",
    "year": "years",
    "years": "years",
}

_RELATIVE_RE = re.compile(r"(\d+)\s*([a-z]+)", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def _subtract_months(d: date, months: int) -> date:
    """Subtracts a whole number of months from `d`, clamping the day to the shorter month."""
    month_index = d.month - 1 - months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    next_month_first = date(year + (month // 12), month % 12 + 1, 1)
    days_in_month = (next_month_first - timedelta(days=1)).day
    return date(year, month, min(d.day, days_in_month))


def parse_posted_date(raw_text: Optional[str], reference: Optional[datetime] = None) -> Optional[str]:
    """
    Converts a scraped "posted date" string (e.g. "3 days ago", "Reposted 2 weeks ago",
    "22h", "Just now", "2023-10-27") into an absolute ISO calendar date (YYYY-MM-DD),
    anchored to `reference` (defaults to now).

    Returns None if the text can't be interpreted as a date, so callers can fall back to
    preserving the original raw text instead of silently dropping it.
    """
    if not raw_text:
        return None

    text = raw_text.strip().lower()
    if not text:
        return None

    ref = reference or datetime.now()

    iso_match = _ISO_DATE_RE.search(text)
    if iso_match:
        try:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))).isoformat()
        except ValueError:
            pass

    if "just now" in text or "just posted" in text or text in ("active", "new"):
        return ref.date().isoformat()

    if "yesterday" in text:
        return (ref - timedelta(days=1)).date().isoformat()

    if "today" in text:
        return ref.date().isoformat()

    match = _RELATIVE_RE.search(text)
    if not match:
        return None

    amount = int(match.group(1))
    unit = _UNIT_ALIASES.get(match.group(2))
    if unit is None:
        return None

    if unit == "months":
        return _subtract_months(ref.date(), amount).isoformat()
    if unit == "years":
        try:
            return ref.date().replace(year=ref.year - amount).isoformat()
        except ValueError:
            # Feb 29 with no matching leap year `amount` years back.
            return ref.date().replace(month=2, day=28, year=ref.year - amount).isoformat()

    return (ref - timedelta(**{unit: amount})).date().isoformat()
