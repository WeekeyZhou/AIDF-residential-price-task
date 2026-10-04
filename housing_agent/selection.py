"""Factor selection by predictive regression.

For each target Y (price or rental index), candidate factor x and horizon h,
two regressions are run. Both were specified before looking at results.

  Lead test (does the factor lead the target?)
      100 * (ln Y[t+h] - ln Y[t]) = a + b * x[t] + e[t+h]

  Strict test (does it add anything beyond the target's own past?)
      the same, plus g[t], ..., g[t-p+1] as controls, where g is the target's
      quarterly log change and the order p is chosen by BIC. This is the
      autoregressive benchmark of an ARIMA / ADL model, and the idea behind a
      Granger causality test.

x[t] is the transformed factor standardised to unit variance. Standard errors
are Newey-West (HAC) because h-quarter-ahead changes overlap, so the errors
are serially correlated by construction.

Within each test, a factor passes if, at its best horizon,
  1. it is significant after Benjamini-Hochberg control of the false discovery
     rate across all factor x horizon tests for that target, and
  2. the sign of b is the same in the first and second half of the sample, and
  3. it is not redundant with a stronger passing factor (|corr| > 0.8).

Evidence tier: "strict" if it passes the strict test, "lead" if it passes only
the lead test, otherwise "none". As a robustness check the same two tests are
run on the first three principal components of the candidate pool.

This is a screening exercise on a small sample. It is not a forecasting model.
"""
from __future__ import annotations

import csv
import math
from datetime import date
from pathlib import Path

import numpy as np

from .config import Config, Indicator
from .fetch import FetchError, download, list_snapshots
from .parse import ParseError, Series, derive_ratio_pct, parse_series

HORIZONS = (1, 2, 4, 8)
MIN_OBS = 40
FDR = 0.10
REDUNDANT = 0.8
MAX_AR = 4
PCA_MIN_OBS = 120


# ---------- data preparation -------------------------------------------------

def to_quarterly(ind: Indicator, series: Series) -> dict:
    """Map a series to {quarter index: value}, quarter index = year * 4 + (q - 1).

    Monthly: last month of the quarter. Annual: the quarter containing the
    reference month, carried forward for the three following quarters.
    """
    out = {}
    for p, v in sorted(series.obs.items()):
        if ind.frequency == "Q":
            out[p.year * 4 + p.n - 1] = v
        elif ind.frequency == "M":
            if p.n % 3 == 0:
                out[p.year * 4 + p.n // 3 - 1] = v
        else:
            t0 = p.year * 4 + (ind.annual_ref_month - 1) // 3
            for k in range(4):  # a later year overwrites the carried-forward value
                out[t0 + k] = v
    return out


def transform(q: dict, kind: str) -> dict:
    if kind == "level":
        return dict(q)
    out = {}
    for t, v in q.items():
        if t - 4 not in q:
            continue
        if kind == "diff4":
            out[t] = v - q[t - 4]
        elif v > 0 and q[t - 4] > 0:
            out[t] = 100 * (math.log(v) - math.log(q[t - 4]))
    return out


def quarter_label(t: int) -> str:
    return f"{t // 4} Q{t % 4 + 1}"


# ---------- econometrics -----------------------------------------------------

def ols_hac(y: np.ndarray, X: np.ndarray, lags: int):
    """OLS with Newey-West (Bartlett kernel) covariance. Returns beta, se, r2."""
    n, k = X.shape
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    u = y - X @ beta
    xu = X * u[:, None]
    S = xu.T @ xu
    for j in range(1, min(lags, n - 1) + 1):
        w = 1 - j / (lags + 1)
        G = xu[j:].T @ xu[:-j]
        S += w * (G + G.T)
    V = xtx_inv @ S @ xtx_inv * n / (n - k)
    tss = float(((y - y.mean()) ** 2).sum())
    return beta, np.sqrt(np.diag(V)), 1 - float(u @ u) / tss if tss else 0.0


def p_value(t: float) -> float:
    """Two-sided p-value from the normal approximation."""
    return math.erfc(abs(t) / math.sqrt(2))


def benjamini_hochberg(pvals: list, q: float = FDR) -> list:
    """Return a list of booleans: which hypotheses are rejected at FDR q."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    cutoff = -1
    for rank, i in enumerate(order, start=1):
        if pvals[i] <= q * rank / m:
            cutoff = rank
    keep = [False] * m
    for rank, i in enumerate(order, start=1):
        keep[i] = rank <= cutoff
    return keep


def growth(target_q: dict) -> dict:
    """Quarterly log change of the target, in per cent."""
    return {t: 100 * (math.log(v) - math.log(target_q[t - 1])) for t, v in target_q.items() if t - 1 in target_q}


def ar_order(target_q: dict, max_p: int = MAX_AR) -> int:
    """Order of the autoregression for the target's quarterly growth, chosen by BIC on a common sample."""
    g = growth(target_q)
    ts = sorted(t for t in g if all(t - j in g for j in range(1, max_p + 1)))
    y = np.array([g[t] for t in ts])
    best, best_bic = 1, math.inf
    for p in range(1, max_p + 1):
        X = np.column_stack([np.ones(len(ts))] + [[g[t - j] for t in ts] for j in range(1, p + 1)])
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        rss = float(((y - X @ beta) ** 2).sum())
        bic = len(ts) * math.log(rss / len(ts)) + (p + 1) * math.log(len(ts))
        if bic < best_bic:
            best, best_bic = p, bic
    return best


def predictive_test(target_q: dict, x: dict, h: int, p: int = 0):
    """One regression from the module docstring; p = 0 is the lead test, p > 0 the strict test.

    Returns a dict, or None if the sample is too short.
    """
    g = growth(target_q)
    ts = sorted(t for t in x if t in target_q and t + h in target_q and all(t - j in g for j in range(p)))
    if len(ts) < MIN_OBS:
        return None
    y = np.array([100 * (math.log(target_q[t + h]) - math.log(target_q[t])) for t in ts])
    xv = np.array([x[t] for t in ts])
    if xv.std() == 0:
        return None
    xs = (xv - xv.mean()) / xv.std()
    ones = np.ones(len(ts))
    controls = [[g[t - j] for t in ts] for j in range(p)]
    X = np.column_stack([ones, xs] + controls)
    if np.linalg.matrix_rank(X) < X.shape[1]:
        return None  # the factor is an exact copy of a control; nothing to test
    lags = max(h - 1, int(4 * (len(ts) / 100) ** (2 / 9)))
    beta, se, r2 = ols_hac(y, X, lags)
    r2_base = ols_hac(y, np.column_stack([ones] + controls), lags)[2] if p else 0.0
    half = len(ts) // 2
    signs = []
    for sl in (slice(0, half), slice(half, None)):
        b, _, _ = ols_hac(y[sl], X[sl], lags)
        signs.append(1 if b[1] > 0 else -1)
    t_stat = float(beta[1] / se[1])
    return {"h": h, "n": len(ts), "start": quarter_label(ts[0]), "end": quarter_label(ts[-1]),
            "beta": float(beta[1]), "t": t_stat, "p": p_value(t_stat), "lags": lags,
            "r2_gain": r2 - r2_base, "sign_first": signs[0], "sign_second": signs[1]}


def correlation(a: dict, b: dict) -> float:
    ts = sorted(set(a) & set(b))
    if len(ts) < MIN_OBS:
        return 0.0
    return float(np.corrcoef([a[t] for t in ts], [b[t] for t in ts])[0, 1])


def run_tier(target_q: dict, factors: dict, p: int, prune: bool = True) -> dict:
    """Run one test (lead if p = 0, strict otherwise) for every factor. Returns {factor id: best-horizon row}."""
    tests = []
    for fid, x in factors.items():
        for h in HORIZONS:
            res = predictive_test(target_q, x, h, p)
            if res:
                tests.append(dict(res, factor=fid))
    for r, ok in zip(tests, benjamini_hochberg([r["p"] for r in tests])):
        r["fdr_pass"] = ok
    rows = {}
    for fid in factors:
        mine = [r for r in tests if r["factor"] == fid]
        if not mine:
            rows[fid] = {"factor": fid, "passed": False, "reason": f"fewer than {MIN_OBS} observations"}
            continue
        best = dict(min(mine, key=lambda r: r["p"]))
        best["stable"] = best["sign_first"] == best["sign_second"]
        best["all"] = sorted(mine, key=lambda r: r["h"])
        if not best["fdr_pass"]:
            best["passed"], best["reason"] = False, "not significant after FDR control"
        elif not best["stable"]:
            best["passed"], best["reason"] = False, "sign differs between sample halves"
        else:
            best["passed"], best["reason"] = True, ""
        rows[fid] = best
    if prune:
        kept = []
        for r in sorted((r for r in rows.values() if r["passed"]), key=lambda r: r["p"]):
            clash = next((k for k in kept if abs(correlation(factors[r["factor"]], factors[k["factor"]])) > REDUNDANT), None)
            if clash:
                r["passed"], r["reason"] = False, f"redundant with {clash['factor']}"
            else:
                kept.append(r)
    return rows


def principal_components(factors: dict, k: int = 3, min_obs: int = PCA_MIN_OBS):
    """First k principal components of the standardised factors that have at least min_obs observations."""
    ids = sorted(f for f, x in factors.items() if len(x) >= min_obs)
    if len(ids) < k + 1:
        return None
    ts = sorted(set.intersection(*(set(factors[f]) for f in ids)))
    if len(ts) < MIN_OBS:
        return None
    Z = np.column_stack([[factors[f][t] for t in ts] for f in ids])
    Z = (Z - Z.mean(axis=0)) / Z.std(axis=0)
    _, s, vt = np.linalg.svd(Z, full_matrices=False)
    comps, loadings = {}, {}
    for i in range(k):
        v = vt[i] if vt[i][np.argmax(np.abs(vt[i]))] > 0 else -vt[i]  # fix the sign so runs agree
        comps[f"PC{i + 1}"] = dict(zip(ts, (Z @ v).tolist()))
        loadings[f"PC{i + 1}"] = dict(zip(ids, v.tolist()))
    share = (s ** 2 / (s ** 2).sum())[:k].tolist()
    return {"components": comps, "loadings": loadings, "share": share, "inputs": ids,
            "sample": f"{quarter_label(ts[0])} to {quarter_label(ts[-1])}", "n": len(ts)}


def select(targets: dict, factors: dict, priors: dict) -> dict:
    """targets: {id: quarterly levels}; factors: {id: transformed quarterly series};
    priors: {factor id: {'sale': sign, 'rent': sign}}.
    Returns {target id: {'ar_order', 'rows': [...], 'pca': {...} or None}}."""
    market = {"price_private": "sale", "rent_private": "rent"}
    pca = principal_components(factors)
    out = {}
    for tid, tq in targets.items():
        p = ar_order(tq)
        lead, strict = run_tier(tq, factors, 0), run_tier(tq, factors, p)
        rows = []
        for fid in factors:
            l, s = lead[fid], strict[fid]
            tier = "strict" if s["passed"] else "lead" if l["passed"] else "none"
            ref = s if tier == "strict" else l
            prior = priors.get(fid, {}).get(market.get(tid, ""), 0)
            agrees = "n/a"
            if prior and "beta" in ref:
                agrees = "yes" if (ref["beta"] > 0) == (prior > 0) else "NO"
            rows.append({"factor": fid, "tier": tier, "lead": l, "strict": s, "agrees": agrees})
        order = {"strict": 0, "lead": 1, "none": 2}
        rows.sort(key=lambda r: (order[r["tier"]], r["lead"].get("p", 9)))
        pcs = None
        if pca:
            pcs = {"lead": run_tier(tq, pca["components"], 0, prune=False),
                   "strict": run_tier(tq, pca["components"], p, prune=False)}
        out[tid] = {"ar_order": p, "rows": rows, "pca": pcs}
    out["_pca"] = pca
    return out


# ---------- pipeline ---------------------------------------------------------

def _load_series(cfg: Config, raw_root: Path, offline: bool, session=None):
    series, problems = {}, {}
    for ind in cfg.indicators:
        if ind.derived:
            continue
        try:
            if offline:
                snaps = list_snapshots(raw_root, ind.id)
                if not snaps:
                    raise FetchError("no stored snapshot")
                snap = snaps[-1]
            else:
                snap = download(cfg, ind, raw_root, session=session)
            series[ind.id] = parse_series(snap.read(), ind)
        except (FetchError, ParseError) as exc:
            problems[ind.id] = str(exc)
    for ind in cfg.indicators:
        if not ind.derived:
            continue
        num, den = ind.derived["numerator"], ind.derived["denominator"]
        if num in series and den in series:
            series[ind.id] = derive_ratio_pct(ind, series[num], series[den])
        else:
            problems[ind.id] = "an input series is unavailable"
    return series, problems


def run_selection(cfg: Config, report_date: date, raw_root: Path, out_root: Path,
                  offline: bool = False, session=None):
    series, problems = _load_series(cfg, raw_root, offline, session)
    cutoff = report_date.year * 4 + (report_date.month - 1) // 3
    targets, factors, priors, names = {}, {}, {}, {}
    for ind in cfg.indicators:
        names[ind.id] = ind.name
        if ind.id not in series:
            continue
        q = {t: v for t, v in to_quarterly(ind, series[ind.id]).items() if t < cutoff}
        if ind.role == "target":
            targets[ind.id] = q
        elif ind.transform:
            factors[ind.id] = transform(q, ind.transform)
            priors[ind.id] = ind.effect
    results = select(targets, factors, priors)
    out_dir = out_root / "selection" / report_date.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    transforms = {ind.id: ind.transform for ind in cfg.indicators}
    (out_dir / "factor_selection.md").write_text(
        render_selection(report_date, results, names, transforms, problems), encoding="utf-8")
    with (out_dir / "factor_tests.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["target", "test", "factor", "horizon_q", "n", "start", "end", "beta_per_sd", "t_hac", "p",
                    "hac_lags", "r2_gain", "fdr_pass", "sign_first_half", "sign_second_half"])
        for tid, res in results.items():
            if tid.startswith("_"):
                continue
            groups = [(test, r[test]) for r in res["rows"] for test in ("lead", "strict")]
            if res["pca"]:
                groups += [(f"{test}_pca", r) for test in ("lead", "strict") for r in res["pca"][test].values()]
            for test, best in groups:
                for a in best.get("all", []):
                    w.writerow([tid, test, a["factor"], a["h"], a["n"], a["start"], a["end"], f"{a['beta']:.4f}",
                                f"{a['t']:.3f}", f"{a['p']:.5f}", a["lags"], f"{a['r2_gain']:.4f}",
                                a["fdr_pass"], a["sign_first"], a["sign_second"]])
    return out_dir, results, problems


def _cell(r: dict) -> str:
    if "p" not in r:
        return "not tested"
    mark = "PASS" if r["passed"] else "fail"
    return f"h={r['h']}, b={r['beta']:+.2f}, t={r['t']:+.2f}, p={r['p']:.4f}, {mark}"


def render_selection(report_date, results, names, transforms, problems) -> str:
    L = [f"# Factor selection: {report_date.isoformat()}", "",
         "Two tests per factor and target, both specified before looking at results. The **lead test** asks "
         "whether the factor leads the h-quarter-ahead change in the target. The **strict test** asks whether it "
         "still does after controlling for the target's own past growth (autoregressive order chosen by BIC). "
         "`b` is the effect, in percentage points of the cumulative h-quarter change, of a one-standard-deviation "
         "rise in the factor. t-statistics use Newey-West standard errors. The horizon shown is the one with the "
         f"smallest p-value among {list(HORIZONS)} quarters. PASS requires significance after Benjamini-Hochberg "
         f"FDR control at {FDR:.0%} across all factor x horizon tests, the same sign in both halves of the sample, "
         f"and no stronger passing factor with |corr| > {REDUNDANT}.", "",
         "Evidence tier: **strict** = passes the strict test; **lead** = passes the lead test only; **none** = neither.", ""]
    pca = results.get("_pca")
    for tid, res in results.items():
        if tid.startswith("_"):
            continue
        L += [f"## Target: {names[tid]}", "", f"Autoregressive order used in the strict test: {res['ar_order']}.", "",
              "| Factor | Transform | Lead test | Strict test | Agrees with prior | Evidence tier | Note |",
              "|---|---|---|---|---|---|---|"]
        for r in res["rows"]:
            f = r["factor"]
            note = r["strict"].get("reason") if r["tier"] == "lead" else r["lead"].get("reason", "") if r["tier"] == "none" else ""
            L.append(f"| {names[f]} | {transforms[f]} | {_cell(r['lead'])} | {_cell(r['strict'])} | {r['agrees']} | "
                     f"{r['tier']} | {note} |")
        if res["pca"]:
            L += ["", "Principal components (robustness check):", "",
                  "| Component | Variance share | Lead test | Strict test |", "|---|---|---|---|"]
            for i, pc in enumerate(pca["components"]):
                L.append(f"| {pc} | {pca['share'][i]:.0%} | {_cell(res['pca']['lead'][pc])} | {_cell(res['pca']['strict'][pc])} |")
        L.append("")
    if pca:
        L += ["## Principal component loadings", "",
              f"Computed on {len(pca['inputs'])} standardised factors with at least {PCA_MIN_OBS} observations, "
              f"sample {pca['sample']} (n = {pca['n']}).", "",
              "| Factor | " + " | ".join(pca["components"]) + " |", "|---|" + "---|" * len(pca["components"])]
        for f in pca["inputs"]:
            L.append(f"| {names[f]} | " + " | ".join(f"{pca['loadings'][pc][f]:+.2f}" for pc in pca["components"]) + " |")
        L.append("")
    if problems:
        L += ["## Candidates that could not be loaded", ""] + [f"- **{k}**: {v}" for k, v in problems.items()] + [""]
    L += ["## Caveats", "",
          "- Small samples (roughly 80 to 200 quarters) and overlapping horizons; p-values use a normal approximation.",
          "- The best horizon is chosen after looking at four horizons; FDR control covers this but does not remove it.",
          "- Passing the lead test only means the factor moves ahead of the target. It may carry no information beyond the target's own momentum.",
          "- Data are today's vintage, not what was known in real time, and publication lags are ignored.",
          "- Policy changes such as cooling measures create structural breaks that these regressions do not model.",
          "- Predictive association is not causation.", ""]
    return "\n".join(L)
