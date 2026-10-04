"""Compute as-of values and changes, with quality flags.

Every change is computed by looking up the exact comparison period, never by
"the previous row". If that period is missing, the change is reported as
unavailable instead of silently comparing against the wrong period.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from .config import Indicator
from .parse import Series
from .periods import Period

CHANGE_UNITS = {"pct": "%", "rate_bp": "bp", "rate_pp": "pp"}
MIN_HISTORY = {"M": 13, "Q": 5, "A": 2}
PREV_LABEL = {"M": "month-on-month", "Q": "quarter-on-quarter", "A": "year-on-year"}


def change(kind: str, current: float, base: float):
    """Change from base to current in the unit implied by kind, or None."""
    if kind == "rate_bp":
        return (current - base) * 100
    if kind == "rate_pp":
        return current - base
    if base == 0:
        return None
    return (current / base - 1) * 100


@dataclass
class Comparison:
    label: str
    period: Period
    value: float | None = None
    raw: str | None = None
    change: float | None = None
    unit: str = ""
    note: str = ""


@dataclass
class Result:
    indicator: Indicator
    status: str = "OK"  # OK, STALE, UNAVAILABLE
    series: Series | None = None
    period: Period | None = None
    value: float | None = None
    raw: str | None = None
    comparisons: list = field(default_factory=list)
    issues: list = field(default_factory=list)  # (level, code, message)
    revisions: list = field(default_factory=list)  # (period, old, new)
    snapshots: list = field(default_factory=list)
    origin: str = ""  # live, stored snapshot, fallback, derived
    error: str = ""

    def comparison(self, label: str) -> Comparison | None:
        for c in self.comparisons:
            if c.label == label:
                return c
        return None


def usable_periods(ind: Indicator, series: Series, report_date: date, retrieved: date) -> list[Period]:
    """Periods that may be used for a report dated report_date.

    A period must have ended by the report date. For a back-dated report the
    typical publication lag is also applied, so a report "as of" a past date
    does not use figures that had not been published yet.
    """
    lag = timedelta(days=ind.pub_lag_days) if report_date < retrieved else timedelta(0)
    return sorted(p for p in series.obs if p.end_date(ind.annual_ref_month) + lag <= report_date)


def analyse(ind: Indicator, series: Series, report_date: date, retrieved: date) -> Result:
    res = Result(indicator=ind, series=series, issues=list(series.issues))
    periods = usable_periods(ind, series, report_date, retrieved)
    if not periods:
        res.status = "UNAVAILABLE"
        res.error = f"no observation available on or before {report_date}"
        return res

    latest = periods[-1]
    res.period, res.value, res.raw = latest, series.obs[latest], series.raw[latest]

    age = (report_date - latest.end_date(ind.annual_ref_month)).days
    if age > ind.max_lag_days:
        res.status = "STALE"
        res.issues.append(("warning", "stale",
                           f"latest observation {latest.label} is {age} days old at the report date "
                           f"(limit {ind.max_lag_days})"))

    if ind.plausible_range and not ind.plausible_range[0] <= res.value <= ind.plausible_range[1]:
        res.issues.append(("warning", "out_of_range",
                           f"{latest.label} value {res.value:g} is outside the plausible range "
                           f"{list(ind.plausible_range)}; check the unit or the source"))

    if len(periods) < MIN_HISTORY[ind.frequency]:
        res.issues.append(("warning", "short_history",
                           f"only {len(periods)} usable observations; some changes cannot be computed"))

    for p in series.missing:
        if p <= latest and p >= latest.year_ago():
            res.issues.append(("warning", "missing_value", f"{p.label} was published without a number ({series.raw[p]!r})"))

    targets = [(PREV_LABEL[ind.frequency], latest.prev())]
    if ind.frequency != "A":
        targets.append(("year-on-year", latest.year_ago()))
    unit = CHANGE_UNITS[ind.unit_kind]
    for label, target in targets:
        comp = Comparison(label=label, period=target, unit=unit)
        if target in series.obs:
            comp.value, comp.raw = series.obs[target], series.raw[target]
            comp.change = change(ind.unit_kind, res.value, comp.value)
            if comp.change is None:
                comp.note = "base value is zero"
            elif ind.seasonal and label != "year-on-year":
                comp.note = "not seasonally adjusted; not interpreted"
        else:
            comp.note = f"{target.label} not in the data"
            res.issues.append(("warning", "gap", f"cannot compute {label} change: {target.label} is missing"))
        res.comparisons.append(comp)
    return res


def find_revisions(old: Series, new: Series, tolerance: float = 1e-9) -> list:
    """Periods present in both vintages whose value changed."""
    return [(p, old.obs[p], new.obs[p]) for p in sorted(set(old.obs) & set(new.obs))
            if abs(old.obs[p] - new.obs[p]) > tolerance]
