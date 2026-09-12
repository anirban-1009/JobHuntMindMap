from datetime import datetime

from src.utils.date_parser import parse_posted_date

REFERENCE = datetime(2026, 8, 23, 10, 0, 0)


def test_none_and_empty_return_none():
    assert parse_posted_date(None, REFERENCE) is None
    assert parse_posted_date("", REFERENCE) is None
    assert parse_posted_date("   ", REFERENCE) is None


def test_unparseable_text_returns_none():
    assert parse_posted_date("gibberish", REFERENCE) is None
    assert parse_posted_date("D", REFERENCE) is None


def test_iso_date_passthrough():
    assert parse_posted_date("2023-10-27", REFERENCE) == "2023-10-27"


def test_relative_days():
    assert parse_posted_date("3 days ago", REFERENCE) == "2026-08-20"
    assert parse_posted_date("3d", REFERENCE) == "2026-08-20"
    assert parse_posted_date("1d", REFERENCE) == "2026-08-22"


def test_relative_weeks():
    assert parse_posted_date("2 weeks ago", REFERENCE) == "2026-08-09"


def test_relative_hours_and_minutes_same_day():
    assert parse_posted_date("22 hours ago", REFERENCE) == "2026-08-22"
    assert parse_posted_date("15 minutes ago", REFERENCE) == "2026-08-23"


def test_relative_months():
    assert parse_posted_date("1 month ago", REFERENCE) == "2026-07-23"
    assert parse_posted_date("5mo", REFERENCE) == "2026-03-23"


def test_relative_years():
    assert parse_posted_date("1 year ago", REFERENCE) == "2025-08-23"
    assert parse_posted_date("1yr", REFERENCE) == "2025-08-23"


def test_today_yesterday_and_just_now():
    assert parse_posted_date("Today", REFERENCE) == "2026-08-23"
    assert parse_posted_date("Yesterday", REFERENCE) == "2026-08-22"
    assert parse_posted_date("Just now", REFERENCE) == "2026-08-23"
    assert parse_posted_date("Active", REFERENCE) == "2026-08-23"


def test_prefix_text_is_ignored():
    assert parse_posted_date("Reposted 2 days ago", REFERENCE) == "2026-08-21"


def test_month_subtraction_clamps_day_to_shorter_month():
    ref = datetime(2026, 3, 30, 10, 0, 0)
    assert parse_posted_date("1 month ago", ref) == "2026-02-28"
