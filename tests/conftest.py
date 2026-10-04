"""Test fixtures: SingStat-shaped payloads and a fake HTTP session.

The payload structure copies the real API (checked on 2026-10-04). The values
are synthetic, except where a comment says otherwise, so tests need no network.
"""
import calendar
import json
from pathlib import Path

import pytest

from housing_agent.config import load_config

ROOT = Path(__file__).resolve().parents[1]
FREQ = {"M": "Monthly", "Q": "Quarterly", "A": "Annual"}


def monthly(start_year, n, first, step):
    out = {}
    for i in range(n):
        y, m = start_year + i // 12, i % 12 + 1
        out[f"{y} {calendar.month_abbr[m]}"] = round(first + step * i, 4)
    return out


def quarterly(start_year, n, first, step):
    return {f"{start_year + i // 4} {i % 4 + 1}Q": round(first + step * i, 4) for i in range(n)}


def annual(start_year, n, first, step):
    return {str(start_year + i): first + step * i for i in range(n)}


def payload(table, freq, rows, status=200, updated="01/09/2026"):
    """rows: list of (seriesNo, rowText, uoM, {period key: value})."""
    return json.dumps({
        "Data": {
            "id": table, "title": f"Test table {table}", "frequency": FREQ[freq],
            "adjustmentType": "", "datasource": "TEST SOURCE", "dataLastUpdated": updated,
            "row": [{"seriesNo": no, "rowText": text, "uoM": unit, "footnote": "",
                     "columns": [{"key": k, "value": str(v)} for k, v in reversed(list(obs.items()))]}
                    for no, text, unit, obs in rows],
        },
        "DataCount": 1, "StatusCode": status, "Message": "",
    }).encode()


def default_tables():
    """One payload per table, covering 2024 to mid-2026."""
    return {
        "M700071": payload("M700071", "M", [
            ("1", "Prime Lending Rate", "Per Cent Per Annum", monthly(2024, 32, 5.25, 0.0)),
            ("21", "Singapore Overnight Rate Average", "Per Cent Per Annum", monthly(2024, 32, 3.50, -0.07)),
            ("23", "Compounded Singapore Overnight Rate Average (SORA) - 3 Month", "Per Cent Per Annum",
             monthly(2024, 32, 3.60, -0.07)),
        ]),
        "M213751": payload("M213751", "M", [("1", "All Items", "Index", monthly(2024, 32, 99.0, 0.1))]),
        "M015651": payload("M015651", "Q", [
            ("1", "GDP At Current Market Prices", "Million Dollars", quarterly(2024, 10, 180000.0, 4000.0)),
        ]),
        "M182342": payload("M182342", "Q", [
            ("1", "Total Unemployment Rate, (SA)", "Per Cent", quarterly(2024, 10, 2.0, 0.0)),
            ("2", "Resident Unemployment Rate, (SA)", "Per Cent", quarterly(2024, 10, 2.7, 0.02)),
        ]),
        "M810001": payload("M810001", "A", [("1", "Total Population", "Number", annual(2020, 7, 5600000, 80000))]),
        "M212161": payload("M212161", "Q", [("1", "HDB Resale Price Index", "Index", quarterly(2024, 10, 180.0, 2.5))]),
        "M400391": payload("M400391", "Q", [
            ("1", "Total Landed Properties", "Number Of Units", quarterly(2024, 10, 1300, 0)),
            ("2", "Total Non-Landed Properties", "Number Of Units", quarterly(2024, 10, 40000, 1200)),
        ]),
        "M400841": payload("M400841", "Q", [
            ("1", "All Types Private Residential Properties Available", "Number Of Units",
             quarterly(2024, 10, 410000, 1500)),
            ("2", "All Types Private Residential Properties Vacant", "Number Of Units",
             quarterly(2024, 10, 30000, -300)),
        ]),
    }


class FakeResponse:
    def __init__(self, status_code, content, url):
        self.status_code, self.content, self.url = status_code, content, url


class FakeSession:
    """Serves payloads by table id. `fail` maps table id -> list of statuses or exceptions to raise first."""

    def __init__(self, tables, fail=None):
        self.tables, self.fail, self.calls = tables, fail or {}, []

    def get(self, url, params=None, timeout=None, headers=None):
        table = url.rsplit("/", 1)[1]
        self.calls.append((table, dict(params or {})))
        queue = self.fail.get(table)
        if queue:
            item = queue.pop(0) if isinstance(queue, list) else queue
            if isinstance(item, Exception):
                raise item
            return FakeResponse(item, b"", url)
        return FakeResponse(200, self.tables[table], url)


@pytest.fixture
def cfg():
    return load_config(ROOT / "tests" / "fixtures" / "indicators.yaml")


@pytest.fixture
def tables():
    return default_tables()


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Retries back off for seconds in real use; tests should not wait."""
    monkeypatch.setattr("housing_agent.fetch.time.sleep", lambda s: None)
