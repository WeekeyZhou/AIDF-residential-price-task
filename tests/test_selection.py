"""Factor selection: the econometrics on data where the right answer is known."""
import numpy as np
import pytest

from housing_agent.config import load_config
from housing_agent.selection import (ar_order, benjamini_hochberg, ols_hac, predictive_test,
                                     principal_components, select, to_quarterly, transform)
from housing_agent.parse import Series
from housing_agent.periods import Period
from conftest import ROOT


def planted(seed=0, n=140):
    """A target whose quarterly growth follows factor `lead` two quarters later; `noise` is unrelated."""
    rng = np.random.default_rng(seed)
    lead, noise = rng.normal(size=n), rng.normal(size=n)
    growth = np.zeros(n)
    growth[2:] = 0.8 * lead[:-2]
    growth += 0.3 * rng.normal(size=n)
    level = 100 * np.exp(np.cumsum(growth) / 100)
    t0 = 1990 * 4
    return ({t0 + i: float(level[i]) for i in range(n)},
            {"lead": {t0 + i: float(lead[i]) for i in range(n)},
             "noise": {t0 + i: float(noise[i]) for i in range(n)}})


def test_ols_matches_least_squares_and_hac_widens_errors_under_autocorrelation():
    rng = np.random.default_rng(1)
    n = 300
    x = np.cumsum(rng.normal(size=n)) * 0.1
    e = np.zeros(n)
    for i in range(1, n):
        e[i] = 0.8 * e[i - 1] + rng.normal()
    y = 1 + 2 * x + e
    X = np.column_stack([np.ones(n), x])
    beta, se0, _ = ols_hac(y, X, 0)
    assert beta == pytest.approx(np.linalg.lstsq(X, y, rcond=None)[0])
    _, se8, _ = ols_hac(y, X, 8)
    assert se8[1] > se0[1]  # ignoring serial correlation would overstate significance


def test_benjamini_hochberg_known_case():
    assert benjamini_hochberg([0.001, 0.02, 0.03, 0.5], q=0.05) == [True, True, True, False]
    assert benjamini_hochberg([0.04, 0.5, 0.6], q=0.05) == [False, False, False]


def test_planted_factor_passes_both_tests_and_noise_passes_neither():
    target, factors = planted()
    res = select({"price_private": target}, factors, {"lead": {"sale": 1}})["price_private"]
    rows = {r["factor"]: r for r in res["rows"]}
    assert rows["lead"]["tier"] == "strict" and rows["lead"]["strict"]["beta"] > 0 and rows["lead"]["agrees"] == "yes"
    assert rows["noise"]["tier"] == "none"


def test_factor_that_only_echoes_past_growth_passes_lead_but_not_strict():
    """A factor that is just the target's own momentum leads the target but adds nothing beyond its past."""
    rng = np.random.default_rng(3)
    n, t0 = 200, 1980 * 4
    g = np.zeros(n)
    for i in range(1, n):
        g[i] = 0.8 * g[i - 1] + rng.normal()
    level = 100 * np.exp(np.cumsum(g) / 100)
    target = {t0 + i: float(level[i]) for i in range(n)}
    echo = {t0 + i: float(g[i] + 0.2 * rng.normal()) for i in range(1, n)}
    row = select({"price_private": target}, {"echo": echo}, {})["price_private"]["rows"][0]
    assert row["lead"]["passed"] and not row["strict"]["passed"] and row["tier"] == "lead"


def test_redundant_factor_is_dropped():
    target, factors = planted()
    factors["copy"] = {t: v * 2 + 0.01 for t, v in factors["lead"].items()}
    rows = {r["factor"]: r for r in select({"price_private": target}, factors, {})["price_private"]["rows"]}
    assert sorted(r["strict"]["passed"] for r in (rows["lead"], rows["copy"])) == [False, True]
    assert "redundant" in (rows["lead"]["strict"]["reason"] + rows["copy"]["strict"]["reason"])


def test_ar_order_recovers_a_second_order_process():
    rng = np.random.default_rng(5)
    g = np.zeros(400)
    for i in range(2, 400):
        g[i] = 0.5 * g[i - 1] + 0.3 * g[i - 2] + rng.normal()
    level = 100 * np.exp(np.cumsum(g) / 100)
    assert ar_order({i: float(v) for i, v in enumerate(level)}) == 2


def test_principal_components_find_the_common_driver():
    rng = np.random.default_rng(7)
    common = rng.normal(size=160)
    factors = {f"f{i}": dict(enumerate((common + 0.3 * rng.normal(size=160)).tolist())) for i in range(4)}
    factors["short"] = dict(enumerate(rng.normal(size=50).tolist()))
    pca = principal_components(factors)
    assert "short" not in pca["inputs"] and pca["share"][0] > 0.8
    pc1 = np.array([pca["components"]["PC1"][t] for t in range(160)])
    assert abs(np.corrcoef(pc1, common)[0, 1]) > 0.95


def test_short_sample_is_not_tested():
    target, factors = planted(n=30)
    assert predictive_test(target, factors["lead"], 1) is None


def test_frequency_conversion_and_transforms():
    cfg = load_config(ROOT / "config" / "candidates.yaml")
    monthly = Series("cpi", obs={Period(2025, m, "M"): float(m) for m in range(1, 13)})
    assert to_quarterly(cfg.get("cpi"), monthly) == {8100: 3.0, 8101: 6.0, 8102: 9.0, 8103: 12.0}
    annual = Series("population", obs={Period(2024, 0, "A"): 10.0, Period(2025, 0, "A"): 11.0})
    q = to_quarterly(cfg.get("population"), annual)  # end-June value, carried forward
    assert q[2024 * 4 + 1] == 10.0 and q[2025 * 4] == 10.0 and q[2025 * 4 + 1] == 11.0
    assert transform({0: 2.0, 4: 2.5}, "diff4") == {4: 0.5}
    assert transform({0: 100.0, 4: 110.0}, "dlog4")[4] == pytest.approx(9.531, abs=1e-3)
