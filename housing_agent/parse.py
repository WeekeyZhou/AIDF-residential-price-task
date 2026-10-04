"""Turn a raw SingStat payload into one clean series, or explain why not."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .config import FREQUENCIES, Indicator
from .periods import Period, parse_period


class ParseError(ValueError):
    """The payload cannot be used for this indicator."""


@dataclass
class Series:
    indicator_id: str
    table_title: str = ""
    row_text: str = ""
    series_no: str = ""
    unit: str = ""
    frequency: str = ""
    adjustment: str = ""
    datasource: str = ""
    data_last_updated: str = ""
    footnote: str = ""
    obs: dict = field(default_factory=dict)  # Period -> float
    raw: dict = field(default_factory=dict)  # Period -> original string
    missing: list = field(default_factory=list)  # periods published without a number
    issues: list = field(default_factory=list)  # (level, code, message)


def _to_number(text: str):
    text = (text or "").strip().replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def parse_series(payload: bytes | str, ind: Indicator) -> Series:
    try:
        doc = json.loads(payload)
    except (ValueError, TypeError) as exc:
        raise ParseError(f"response is not JSON: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("StatusCode") != 200 or not isinstance(doc.get("Data"), dict):
        status = doc.get("StatusCode") if isinstance(doc, dict) else None
        message = doc.get("Message") if isinstance(doc, dict) else None
        raise ParseError(f"API reported failure: StatusCode={status} Message={message!r}")
    data = doc["Data"]
    rows = data.get("row") or []
    row = _select_row(rows, ind)

    s = Series(
        indicator_id=ind.id,
        table_title=data.get("title") or "",
        row_text=row.get("rowText") or "",
        series_no=str(row.get("seriesNo") or ""),
        unit=row.get("uoM") or "",
        frequency=data.get("frequency") or "",
        adjustment=data.get("adjustmentType") or "",
        datasource=data.get("datasource") or "",
        data_last_updated=data.get("dataLastUpdated") or "",
        footnote=(row.get("footnote") or "").strip(),
    )

    expected_freq = FREQUENCIES[ind.frequency]
    if s.frequency != expected_freq:
        raise ParseError(f"frequency is {s.frequency!r}, expected {expected_freq!r}")
    if ind.expected_unit and s.unit != ind.expected_unit:
        # A unit change would make every computed change wrong without any
        # visible error, so this is fatal rather than a warning.
        raise ParseError(f"unit is {s.unit!r}, expected {ind.expected_unit!r}")

    for col in row.get("columns") or []:
        key = col.get("key", "")
        try:
            period = parse_period(key)
        except ValueError as exc:
            s.issues.append(("warning", "bad_period", str(exc)))
            continue
        if period.freq != ind.frequency:
            s.issues.append(("warning", "bad_period", f"period {key!r} is not {expected_freq}"))
            continue
        if period in s.raw:
            s.issues.append(("warning", "duplicate_period", f"{period.label} appears more than once; first value kept"))
            continue
        s.raw[period] = col.get("value", "")
        value = _to_number(col.get("value", ""))
        if value is None:
            s.missing.append(period)
        else:
            s.obs[period] = value
    if not s.obs:
        raise ParseError("series has no numeric observations")
    return s


def _select_row(rows: list, ind: Indicator) -> dict:
    """Pick the row by its text, not only by position or number.

    Series numbers are positional inside a table and can shift when the
    publisher adds a row, so the row text must also match when a pattern is
    configured.
    """
    candidates = rows
    if ind.series_no:
        candidates = [r for r in candidates if str(r.get("seriesNo")) == ind.series_no]
    if ind.row_match:
        pattern = re.compile(ind.row_match)
        candidates = [r for r in candidates if pattern.search(r.get("rowText") or "")]
    if len(candidates) == 1:
        return candidates[0]
    available = "; ".join(f"{r.get('seriesNo')}={r.get('rowText')!r}" for r in rows[:40]) or "none"
    problem = "no row matches" if not candidates else f"{len(candidates)} rows match"
    raise ParseError(
        f"{problem} series_no={ind.series_no!r} row_match={ind.row_match!r}. Rows returned: {available}"
    )


def derive_ratio_pct(ind: Indicator, numerator: Series, denominator: Series) -> Series:
    s = Series(
        indicator_id=ind.id,
        table_title="Derived by this workflow",
        row_text=f"{numerator.row_text} / {denominator.row_text} x 100",
        unit="Per Cent",
        frequency=FREQUENCIES[ind.frequency],
        datasource=numerator.datasource,
        data_last_updated=numerator.data_last_updated,
    )
    for period in sorted(set(numerator.obs) & set(denominator.obs)):
        if denominator.obs[period] == 0:
            s.missing.append(period)
            continue
        s.obs[period] = numerator.obs[period] / denominator.obs[period] * 100
        s.raw[period] = f"{s.obs[period]:.4f} ({numerator.raw[period]} / {denominator.raw[period]} x 100)"
    if not s.obs:
        raise ParseError("no period has both numerator and denominator")
    return s
