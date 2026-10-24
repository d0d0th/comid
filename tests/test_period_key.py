"""Tests for Comid.period_key across all six period types, including the fortnight rule
and a fixed timestamp right at the 23:30 UTC boundary of July 31st."""

from datetime import datetime, timezone

import pytest

from comid import Comid

JULY_31_2330_UTC = datetime(2024, 7, 31, 23, 30, tzinfo=timezone.utc).timestamp()


@pytest.mark.parametrize(
    "period_type,expected",
    [
        ("d", "2024-07-31"),
        ("m", "2024-07"),
        ("f", "2024-07-F2"),  # day=31 >= 15 -> second fortnight
        ("q", "2024-Q3"),  # July is in Q3 (months 7-9)
        ("y", "2024"),
    ],
)
def test_period_key_five_types_at_july_31_2330_utc(period_type, expected):
    assert Comid.period_key(JULY_31_2330_UTC, period_type) == expected


def test_period_key_week_type_at_july_31_2330_utc():
    expected = datetime(2024, 7, 31, 23, 30, tzinfo=timezone.utc).strftime("%Y-%W")
    assert Comid.period_key(JULY_31_2330_UTC, "w") == expected


@pytest.mark.parametrize(
    "day,expected_suffix",
    [
        (1, "-F1"),
        (14, "-F1"),
        (15, "-F2"),
        (31, "-F2"),
    ],
)
def test_period_key_fortnight_boundary_rule(day, expected_suffix):
    ts = datetime(2024, 3, day, tzinfo=timezone.utc).timestamp()
    assert Comid.period_key(ts, "f") == "2024-03" + expected_suffix


def test_period_key_is_case_insensitive():
    assert Comid.period_key(JULY_31_2330_UTC, "M") == Comid.period_key(JULY_31_2330_UTC, "m")


def test_period_key_invalid_period_type_raises():
    with pytest.raises(Exception):
        Comid.period_key(JULY_31_2330_UTC, "invalid")
