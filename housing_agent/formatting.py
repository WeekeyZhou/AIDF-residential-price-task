"""One place for how numbers are printed, so the report and the checks agree."""
from __future__ import annotations


def fmt_value(unit: str, value: float) -> str:
    if unit in ("Per Cent", "Per Cent Per Annum"):
        return f"{value:.2f}%"
    if unit == "Index":
        return f"{value:.3f}"
    if unit == "Million Dollars":
        return f"S${value:,.1f} million"
    return f"{value:,.0f}"


def fmt_change(unit: str, change: float | None) -> str:
    if change is None:
        return "n/a"
    if unit == "bp":
        return f"{change:+.1f} bp"
    if unit == "pp":
        return f"{change:+.2f} pp"
    return f"{change:+.2f}%"


def formula(kind: str, current_raw: str, base_raw: str) -> str:
    if kind == "rate_bp":
        return f"({current_raw} - {base_raw}) x 100"
    if kind == "rate_pp":
        return f"{current_raw} - {base_raw}"
    return f"({current_raw} / {base_raw} - 1) x 100"
