"""Calendar periods as published by SingStat: '2026 Jan', '2026 2Q', '2026'."""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

_MONTHS = {m: i for i, m in enumerate(calendar.month_abbr) if m}
_RE_M = re.compile(r"^(\d{4}) ([A-Z][a-z]{2})$")
_RE_Q = re.compile(r"^(\d{4}) ([1-4])Q$")
_RE_A = re.compile(r"^(\d{4})$")


@dataclass(frozen=True, order=True)
class Period:
    """freq is 'M', 'Q' or 'A'; n is month (1-12), quarter (1-4) or 0."""

    year: int
    n: int
    freq: str

    @property
    def label(self) -> str:
        if self.freq == "M":
            return f"{self.year} {calendar.month_abbr[self.n]}"
        if self.freq == "Q":
            return f"{self.year} Q{self.n}"
        return str(self.year)

    def prev(self) -> "Period":
        if self.freq == "A":
            return Period(self.year - 1, 0, "A")
        size = 12 if self.freq == "M" else 4
        if self.n == 1:
            return Period(self.year - 1, size, self.freq)
        return Period(self.year, self.n - 1, self.freq)

    def year_ago(self) -> "Period":
        return Period(self.year - 1, self.n, self.freq)

    def end_date(self, annual_ref_month: int = 12) -> date:
        if self.freq == "M":
            month = self.n
        elif self.freq == "Q":
            month = self.n * 3
        else:
            month = annual_ref_month
        return date(self.year, month, calendar.monthrange(self.year, month)[1])


def parse_period(key: str) -> Period:
    """Parse a SingStat column key. Raises ValueError on any other format."""
    key = key.strip()
    if m := _RE_M.match(key):
        if m.group(2) not in _MONTHS:
            raise ValueError(f"unknown month in period key {key!r}")
        return Period(int(m.group(1)), _MONTHS[m.group(2)], "M")
    if m := _RE_Q.match(key):
        return Period(int(m.group(1)), int(m.group(2)), "Q")
    if m := _RE_A.match(key):
        return Period(int(m.group(1)), 0, "A")
    raise ValueError(f"unrecognised period key {key!r}")
