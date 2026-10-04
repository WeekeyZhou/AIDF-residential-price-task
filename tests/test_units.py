"""Periods, parsing, and change calculations."""
from datetime import date

import pytest

from conftest import monthly, payload, quarterly
from housing_agent.analyse import analyse, change, find_revisions
from housing_agent.parse import ParseError, parse_series
from housing_agent.periods import Period, parse_period

TODAY = date(2026, 10, 4)


def test_period_keys_and_arithmetic():
    assert parse_period("2026 Jan") == Period(2026, 1, "M")
    assert parse_period("2026 2Q") == Period(2026, 2, "Q")
    assert parse_period("2026") == Period(2026, 0, "A")
    assert parse_period("2026 Jan").prev() == Period(2025, 12, "M")
    assert parse_period("2026 1Q").prev() == Period(2025, 4, "Q")
    assert parse_period("2024 Feb").end_date() == date(2024, 2, 29)
    assert parse_period("2026").end_date(annual_ref_month=6) == date(2026, 6, 30)
    with pytest.raises(ValueError):
        parse_period("Jan 2026")


def test_changes_use_the_right_unit():
    assert change("rate_bp", 2.75, 3.00) == pytest.approx(-25.0)   # basis points
    assert change("rate_pp", 2.9, 2.7) == pytest.approx(0.2)       # percentage points
    assert change("pct", 102.0, 100.0) == pytest.approx(2.0)       # per cent
    assert change("pct", 5.0, 0.0) is None


def test_values_and_changes_end_to_end(cfg, tables):
    ind = cfg.get("sora")
    res = analyse(ind, parse_series(tables["M700071"], ind), TODAY, TODAY)
    assert res.period.label == "2026 Aug" and res.status == "OK"
    assert res.comparison("month-on-month").change == pytest.approx(-7.0)
    assert res.comparison("year-on-year").change == pytest.approx(-84.0)
    assert res.comparison("year-on-year").unit == "bp"


def test_row_is_selected_by_text_not_only_by_number(cfg):
    """If the publisher inserts a row, series numbers shift. That must fail loudly."""
    ind = cfg.get("unemployment_resident")
    shifted = payload("M182342", "Q", [
        ("1", "Total Unemployment Rate, (SA)", "Per Cent", quarterly(2024, 10, 2.0, 0)),
        ("2", "New Inserted Rate", "Per Cent", quarterly(2024, 10, 9.9, 0)),
        ("3", "Resident Unemployment Rate, (SA)", "Per Cent", quarterly(2024, 10, 2.7, 0)),
    ])
    with pytest.raises(ParseError, match="no row matches"):
        parse_series(shifted, ind)


def test_unit_change_is_fatal(cfg):
    ind = cfg.get("gdp_nominal")
    bad = payload("M015651", "Q", [("1", "GDP At Current Market Prices", "Billion Dollars",
                                    quarterly(2024, 10, 180.0, 4.0))])
    with pytest.raises(ParseError, match="unit is 'Billion Dollars'"):
        parse_series(bad, ind)


def test_error_body_with_http_200_is_rejected(cfg):
    ind = cfg.get("cpi")
    with pytest.raises(ParseError, match="API reported failure"):
        parse_series(b'{"Data": null, "StatusCode": 404, "Message": "Resource not found"}', ind)
    with pytest.raises(ParseError, match="not JSON"):
        parse_series(b"<html>Service unavailable</html>", ind)


def test_gap_gives_no_change_instead_of_a_wrong_one(cfg):
    """A missing month must not make 'previous row' silently become month-on-month."""
    ind = cfg.get("cpi")
    obs = monthly(2024, 32, 99.0, 0.1)
    obs["2026 Jul"] = "na"
    res = analyse(ind, parse_series(payload("M213751", "M", [("1", "All Items", "Index", obs)]), ind), TODAY, TODAY)
    mom = res.comparison("month-on-month")
    assert res.period.label == "2026 Aug"
    assert mom.change is None and "2026 Jul" in mom.note
    assert res.comparison("year-on-year").change is not None
    assert {"gap", "missing_value"} <= {code for _, code, _ in res.issues}


def test_report_date_excludes_later_data(cfg, tables):
    ind = cfg.get("cpi")
    series = parse_series(tables["M213751"], ind)
    assert analyse(ind, series, date(2026, 3, 31), date(2026, 3, 31)).period.label == "2026 Mar"
    # Back-dated report run later: March CPI was not yet published on 5 April (25-day lag).
    assert analyse(ind, series, date(2026, 4, 5), TODAY).period.label == "2026 Feb"


def test_stale_series_is_flagged(cfg, tables):
    ind = cfg.get("cpi")
    res = analyse(ind, parse_series(tables["M213751"], ind), date(2027, 1, 15), date(2027, 1, 15))
    assert res.status == "STALE" and res.period.label == "2026 Aug"


def test_out_of_range_value_is_flagged(cfg):
    ind = cfg.get("unemployment_resident")
    obs = quarterly(2024, 10, 2.7, 0.0)
    obs["2026 2Q"] = 29  # e.g. 2.9 published without its decimal point
    res = analyse(ind, parse_series(payload("M182342", "Q", [
        ("2", "Resident Unemployment Rate, (SA)", "Per Cent", obs)]), ind), TODAY, TODAY)
    assert "out_of_range" in {code for _, code, _ in res.issues}


def test_revisions_between_vintages_are_found(cfg):
    ind = cfg.get("gdp_nominal")
    old = quarterly(2024, 9, 180000.0, 4000.0)
    new = dict(quarterly(2024, 10, 180000.0, 4000.0), **{"2026 1Q": 212500.0})
    row = lambda obs: payload("M015651", "Q", [("1", "GDP At Current Market Prices", "Million Dollars", obs)])
    revisions = find_revisions(parse_series(row(old), ind), parse_series(row(new), ind))
    assert [(p.label, a, b) for p, a, b in revisions] == [("2026 Q1", 212000.0, 212500.0)]
