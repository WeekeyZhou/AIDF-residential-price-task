"""Load and check the indicator registry."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

UNIT_KINDS = {"pct", "rate_bp", "rate_pp"}
FREQUENCIES = {"M": "Monthly", "Q": "Quarterly", "A": "Annual"}


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Indicator:
    id: str
    name: str
    frequency: str
    unit_kind: str
    max_lag_days: int
    table: str | None = None
    series_no: str | None = None
    row_match: str | None = None
    expected_unit: str | None = None
    derived: dict | None = None
    annual_ref_month: int = 12
    pub_lag_days: int = 0
    seasonal: bool = False
    report: bool = True
    plausible_range: tuple | None = None
    effect: dict = field(default_factory=dict)
    definition: str = ""
    rationale: str = ""


@dataclass(frozen=True)
class Config:
    source_name: str
    base_url: str
    limit: int
    indicators: tuple

    def get(self, indicator_id: str) -> Indicator:
        for ind in self.indicators:
            if ind.id == indicator_id:
                return ind
        raise KeyError(indicator_id)


def load_config(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    indicators = []
    seen = set()
    for item in raw["indicators"]:
        item = dict(item)
        if "plausible_range" in item:
            item["plausible_range"] = tuple(item["plausible_range"])
        if "series_no" in item:
            item["series_no"] = str(item["series_no"])
        try:
            ind = Indicator(**item)
        except TypeError as exc:
            raise ConfigError(f"indicator {item.get('id')}: {exc}") from exc
        if ind.id in seen:
            raise ConfigError(f"duplicate indicator id {ind.id}")
        seen.add(ind.id)
        if ind.unit_kind not in UNIT_KINDS:
            raise ConfigError(f"{ind.id}: unit_kind must be one of {sorted(UNIT_KINDS)}")
        if ind.frequency not in FREQUENCIES:
            raise ConfigError(f"{ind.id}: frequency must be M, Q or A")
        if bool(ind.table) == bool(ind.derived):
            raise ConfigError(f"{ind.id}: give exactly one of 'table' or 'derived'")
        if ind.table and not (ind.series_no or ind.row_match):
            raise ConfigError(f"{ind.id}: needs series_no or row_match")
        indicators.append(ind)
    for ind in indicators:
        if ind.derived:
            for key in ("numerator", "denominator"):
                if ind.derived.get(key) not in seen:
                    raise ConfigError(f"{ind.id}: unknown {key} {ind.derived.get(key)!r}")
    src = raw["source"]
    return Config(src["name"], src["base_url"].rstrip("/"), int(src["limit"]), tuple(indicators))
