"""Download behaviour, failure handling, reproducibility, and the LLM check."""
import json
from datetime import date

import pytest
import requests

from conftest import FakeSession, monthly, payload
from housing_agent.fetch import FetchError, download, list_snapshots
from housing_agent.narrative import build_facts, write_commentary
from housing_agent.pipeline import run

D = date(2026, 10, 4)


def go(cfg, tmp_path, session=None, **kw):
    return run(cfg, D, tmp_path / "raw", tmp_path / "out", session=session, **kw)


def test_full_run_writes_report_and_snapshots(cfg, tables, tmp_path):
    out, results, code = go(cfg, tmp_path, FakeSession(tables))
    report = (out / "report.md").read_text(encoding="utf-8")
    assert code == 0 and {r.status for r in results} == {"OK"}
    assert "-84.0 bp" in report and "(1.43 - 2.27) x 100" in report  # figure and its inputs
    manifest = json.loads((out / "manifest.json").read_text())
    assert len(manifest["snapshots"]) == 8
    snap = list_snapshots(tmp_path / "raw", "cpi")[0]
    assert snap.read() == tables["M213751"]  # raw bytes kept exactly


def test_vacancy_rate_is_derived_from_its_two_inputs(cfg, tables, tmp_path):
    _, results, _ = go(cfg, tmp_path, FakeSession(tables))
    vac = next(r for r in results if r.indicator.id == "vacancy_rate")
    assert vac.value == pytest.approx(27300 / 423500 * 100)
    assert vac.comparison("year-on-year").unit == "pp"


def test_retries_transient_errors_but_not_client_errors(cfg, tables, tmp_path):
    ind = cfg.get("cpi")
    flaky = FakeSession(tables, fail={"M213751": [503, requests.ConnectionError("reset")]})
    assert download(cfg, ind, tmp_path, session=flaky).read() == tables["M213751"]
    assert len(flaky.calls) == 3
    missing = FakeSession(tables, fail={"M213751": [404, 404, 404]})
    with pytest.raises(FetchError, match="HTTP 404"):
        download(cfg, ind, tmp_path, session=missing)
    assert len(missing.calls) == 1


def test_failed_download_falls_back_to_last_snapshot_and_says_so(cfg, tables, tmp_path):
    go(cfg, tmp_path, FakeSession(tables))
    out, results, code = go(cfg, tmp_path, FakeSession(tables, fail={"M213751": 503}))
    cpi = next(r for r in results if r.indicator.id == "cpi")
    assert code == 1 and cpi.status == "OK" and "FALLBACK" in cpi.origin
    assert "download_failed" in (out / "report.md").read_text(encoding="utf-8")


def test_no_data_at_all_still_produces_a_report(cfg, tables, tmp_path):
    out, results, code = go(cfg, tmp_path, FakeSession(tables, fail={"M400841": 503}))
    status = {r.indicator.id: r.status for r in results}
    assert code == 2 and status["vacancy_rate"] == "UNAVAILABLE" and status["cpi"] == "OK"
    assert "| Private Residential Vacancy Rate | UNAVAILABLE | n/a | n/a | n/a | n/a | n/a | n/a |" in \
        (out / "report.md").read_text(encoding="utf-8")


def test_bad_payload_is_rejected_and_previous_snapshot_used(cfg, tables, tmp_path):
    go(cfg, tmp_path, FakeSession(tables))
    broken = dict(tables, M213751=b'{"Data": null, "StatusCode": 500, "Message": "error"}')
    _, results, code = go(cfg, tmp_path, FakeSession(broken))
    cpi = next(r for r in results if r.indicator.id == "cpi")
    assert code == 1 and cpi.period.label == "2026 Aug"
    assert "bad_payload" in {c for _, c, _ in cpi.issues}


def test_report_is_reproducible_from_its_manifest(cfg, tables, tmp_path):
    out, _, _ = go(cfg, tmp_path, FakeSession(tables))
    first = (out / "report.md").read_bytes()
    manifest = tmp_path / "manifest_copy.json"
    manifest.write_bytes((out / "manifest.json").read_bytes())
    # The source publishes a new month and revises history. A later snapshot now exists...
    revised = dict(tables, M213751=payload("M213751", "M", [("1", "All Items", "Index", monthly(2024, 33, 99.5, 0.1))]))
    go(cfg, tmp_path, FakeSession(revised))
    assert (out / "report.md").read_bytes() != first
    # ...but the original report can still be recreated byte for byte, with no network.
    go(cfg, tmp_path, session=None, manifest_path=manifest)
    assert (out / "report.md").read_bytes() == first


def test_revision_is_reported(cfg, tables, tmp_path):
    go(cfg, tmp_path, FakeSession(tables))
    obs = monthly(2024, 32, 99.0, 0.1)
    obs["2026 Jul"] = 102.5
    revised = dict(tables, M213751=payload("M213751", "M", [("1", "All Items", "Index", obs)]))
    out, _, _ = go(cfg, tmp_path, FakeSession(revised))
    assert "revision: 2026 Jul changed from 102 to 102.5" in (out / "report.md").read_text(encoding="utf-8")


def test_truncated_history_is_flagged_not_hidden(cfg, tables, tmp_path):
    """The API's `limit` counts cells across all rows, so a big table can come back with too few periods."""
    short = dict(tables, M213751=payload("M213751", "M", [("1", "All Items", "Index", monthly(2026, 8, 101.4, 0.1))]))
    _, results, _ = go(cfg, tmp_path, FakeSession(short))
    cpi = next(r for r in results if r.indicator.id == "cpi")
    assert cpi.comparison("year-on-year").change is None
    assert {"short_history", "gap"} <= {c for _, c, _ in cpi.issues}


def test_series_filter_is_sent_so_history_is_not_truncated(cfg, tables, tmp_path):
    session = FakeSession(tables)
    go(cfg, tmp_path, session)
    assert ("M213751", {"limit": 2000, "sortBy": "key desc", "seriesNoORrowNo": "1"}) in session.calls


def test_llm_text_with_an_invented_number_is_rejected(cfg, tables, tmp_path):
    _, results, _ = go(cfg, tmp_path, FakeSession(tables))
    facts = build_facts([r for r in results if r.indicator.report])
    invented = write_commentary(facts, llm=lambda prompt: "SORA fell 84.0 bp, so prices should rise 5.5% next year.")
    assert invented["sale"]["mode"] == "template" and "5.5" in invented["sale"]["note"]
    grounded = write_commentary(facts, llm=lambda prompt: "Funding costs eased: SORA is down 84.0 bp on the year.")
    assert grounded["sale"]["mode"] == "llm"

    def boom(prompt):
        raise TimeoutError("api down")
    assert write_commentary(facts, llm=boom)["rent"]["mode"] == "template"


def test_production_registry_runs_and_reads_only_factors_with_evidence(tables, tmp_path):
    from conftest import ROOT
    from housing_agent.config import load_config
    prod = load_config(ROOT / "config" / "indicators.yaml")
    out, results, code = run(prod, D, tmp_path / "raw", tmp_path / "out", session=FakeSession(tables))
    assert code == 0
    for ind in prod.indicators:  # a market is read if and only if the screening gave it an evidence tier
        for market in ("sale", "rent"):
            assert bool(ind.effect.get(market)) == (market in ind.evidence), (ind.id, market)
    facts = build_facts([r for r in results if r.indicator.report])
    assert [r["id"] for r in facts["sale"]["readings"]] == ["vacancy_rate", "gdp_nominal", "hdb_resale", "sora"]
    assert [r["id"] for r in facts["rent"]["readings"]] == ["vacancy_rate", "gdp_nominal", "unemployment_resident"]
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "| lead / strict | upward | upward |" in report          # vacancy rate fell: supportive for both
    assert "| monitored only | not used | not used |" in report      # supply pipeline is not read
    assert "| prior / not used | upward | not used |" in report      # SORA fell: read for sale only


def test_stale_and_llm_notes_stay_visible_without_a_status_column(cfg, tables, tmp_path):
    from datetime import date
    out, _, code = run(cfg, date(2027, 6, 1), tmp_path / "raw", tmp_path / "out", session=FakeSession(tables),
                       llm=lambda prompt: "Prices will rise 9.9% next year.")
    report = (out / "report.md").read_text(encoding="utf-8")
    assert code == 1 and "| 2026 Aug (STALE) |" in report
    assert "## 2. Indicators and traceability" in report           # no commentary section when the LLM text is rejected
    assert "**commentary (sale)**: LLM text rejected" in report
