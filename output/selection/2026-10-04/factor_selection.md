# Factor selection: 2026-10-04

Two tests per factor and target, both specified before looking at results. The **lead test** asks whether the factor leads the h-quarter-ahead change in the target. The **strict test** asks whether it still does after controlling for the target's own past growth (autoregressive order chosen by BIC). `b` is the effect, in percentage points of the cumulative h-quarter change, of a one-standard-deviation rise in the factor. t-statistics use Newey-West standard errors. The horizon shown is the one with the smallest p-value among [1, 2, 4, 8] quarters. PASS requires significance after Benjamini-Hochberg FDR control at 10% across all factor x horizon tests, the same sign in both halves of the sample, and no stronger passing factor with |corr| > 0.8.

Evidence tier: **strict** = passes the strict test; **lead** = passes the lead test only; **none** = neither.

## Target: Private Residential Property Price Index

Autoregressive order used in the strict test: 1.

| Factor | Transform | Lead test | Strict test | Agrees with prior | Evidence tier | Note |
|---|---|---|---|---|---|---|
| Real GDP, seasonally adjusted | dlog4 | h=1, b=+1.78, t=+3.54, p=0.0004, PASS | h=4, b=-1.00, t=-0.69, p=0.4909, fail | yes | lead | not significant after FDR control |
| Private Vacancy Rate (4-quarter change) | diff4 | h=1, b=-1.45, t=-2.82, p=0.0049, PASS | h=1, b=-0.69, t=-2.37, p=0.0177, fail | yes | lead | not significant after FDR control |
| HDB Resale Price Index | dlog4 | h=1, b=+1.59, t=+2.52, p=0.0116, PASS | h=2, b=+0.75, t=+0.63, p=0.5312, fail | yes | lead | not significant after FDR control |
| Private Non-Landed Supply Pipeline | dlog4 | h=1, b=+1.26, t=+2.49, p=0.0130, PASS | h=8, b=-4.89, t=-1.39, p=0.1631, fail | NO | lead | not significant after FDR control |
| GDP at Current Market Prices | dlog4 | h=1, b=+1.96, t=+3.16, p=0.0016, fail | h=1, b=+0.36, t=+1.21, p=0.2261, fail | yes | none | redundant with gdp_real |
| Vacant Completed Private Homes | dlog4 | h=1, b=-1.24, t=-2.46, p=0.0140, fail | h=1, b=-0.60, t=-2.20, p=0.0278, fail | yes | none | redundant with vacancy_change |
| Consumer Price Index, All Items | dlog4 | h=8, b=+6.51, t=+1.95, p=0.0514, fail | h=8, b=+4.43, t=+1.89, p=0.0594, fail | yes | none | not significant after FDR control |
| Private Vacancy Rate (level) | level | h=1, b=-1.04, t=-1.93, p=0.0540, fail | h=2, b=-0.68, t=-0.89, p=0.3726, fail | yes | none | not significant after FDR control |
| 2-Year Government Bond Yield | diff4 | h=2, b=-1.57, t=-1.51, p=0.1319, fail | h=2, b=-1.07, t=-1.60, p=0.1086, fail | yes | none | not significant after FDR control |
| Resident Unemployment Rate (SA) | diff4 | h=1, b=-0.58, t=-1.42, p=0.1566, fail | h=4, b=+4.03, t=+2.44, p=0.0145, fail | yes | none | not significant after FDR control |
| Total Unemployment Rate (SA) | diff4 | h=1, b=-0.55, t=-1.39, p=0.1640, fail | h=4, b=+4.10, t=+2.43, p=0.0149, fail | yes | none | not significant after FDR control |
| Completed Private Homes (stock growth) | dlog4 | h=8, b=-2.43, t=-1.38, p=0.1670, fail | h=8, b=-2.60, t=-1.56, p=0.1198, fail | yes | none | not significant after FDR control |
| 3-Month Compounded SORA | diff4 | h=4, b=+1.40, t=+0.82, p=0.4126, fail | h=2, b=+0.68, t=+0.82, p=0.4094, fail | NO | none | not significant after FDR control |
| Total Population | dlog4 | h=2, b=-0.58, t=-0.69, p=0.4931, fail | h=1, b=-0.22, t=-0.90, p=0.3671, fail | NO | none | not significant after FDR control |
| 10-Year Government Bond Yield | diff4 | h=8, b=+0.83, t=+0.50, p=0.6144, fail | h=1, b=-0.20, t=-0.96, p=0.3357, fail | NO | none | not significant after FDR control |
| Exchange Rate, SGD per USD | dlog4 | not tested | not tested | n/a | none | fewer than 40 observations |

Principal components (robustness check):

| Component | Variance share | Lead test | Strict test |
|---|---|---|---|
| PC1 | 35% | h=1, b=-1.33, t=-2.65, p=0.0080, PASS | h=8, b=+3.42, t=+1.20, p=0.2320, fail |
| PC2 | 16% | h=4, b=-5.64, t=-2.43, p=0.0152, PASS | h=1, b=-0.86, t=-2.52, p=0.0118, PASS |
| PC3 | 15% | h=4, b=-1.31, t=-0.73, p=0.4661, fail | h=4, b=-1.07, t=-0.63, p=0.5278, fail |

## Target: Private Residential Rental Index

Autoregressive order used in the strict test: 1.

| Factor | Transform | Lead test | Strict test | Agrees with prior | Evidence tier | Note |
|---|---|---|---|---|---|---|
| GDP at Current Market Prices | dlog4 | h=1, b=+1.70, t=+3.99, p=0.0001, PASS | h=1, b=+0.68, t=+3.02, p=0.0025, PASS | yes | strict |  |
| Private Vacancy Rate (4-quarter change) | diff4 | h=4, b=-5.62, t=-3.19, p=0.0014, PASS | h=1, b=-0.84, t=-3.70, p=0.0002, PASS | yes | strict |  |
| Private Vacancy Rate (level) | level | h=1, b=-1.50, t=-3.15, p=0.0017, PASS | h=1, b=-0.69, t=-2.57, p=0.0102, PASS | yes | strict |  |
| Resident Unemployment Rate (SA) | diff4 | h=1, b=-1.43, t=-3.44, p=0.0006, PASS | h=1, b=-0.21, t=-0.77, p=0.4386, fail | yes | lead | not significant after FDR control |
| Private Non-Landed Supply Pipeline | dlog4 | h=1, b=+1.56, t=+3.05, p=0.0023, PASS | h=1, b=+0.34, t=+1.78, p=0.0756, fail | NO | lead | not significant after FDR control |
| Total Unemployment Rate (SA) | diff4 | h=2, b=-2.36, t=-3.36, p=0.0008, fail | h=1, b=-0.18, t=-0.65, p=0.5157, fail | yes | none | redundant with unemployment_resident |
| Vacant Completed Private Homes | dlog4 | h=4, b=-5.67, t=-3.16, p=0.0016, fail | h=4, b=-4.72, t=-3.32, p=0.0009, fail | yes | none | redundant with vacancy_change |
| Real GDP, seasonally adjusted | dlog4 | h=1, b=+1.34, t=+2.97, p=0.0030, fail | h=1, b=+0.33, t=+1.76, p=0.0783, fail | yes | none | redundant with gdp_nominal |
| Completed Private Homes (stock growth) | dlog4 | h=8, b=-4.40, t=-1.94, p=0.0528, fail | h=8, b=-4.14, t=-2.18, p=0.0289, fail | yes | none | not significant after FDR control |
| Total Population | dlog4 | h=8, b=-5.26, t=-1.91, p=0.0559, fail | h=8, b=-5.35, t=-2.19, p=0.0282, fail | NO | none | not significant after FDR control |
| Consumer Price Index, All Items | dlog4 | h=1, b=+0.84, t=+1.65, p=0.0990, fail | h=8, b=-2.12, t=-1.10, p=0.2709, fail | yes | none | not significant after FDR control |
| 10-Year Government Bond Yield | diff4 | h=1, b=+0.75, t=+1.63, p=0.1032, fail | h=1, b=+0.13, t=+0.94, p=0.3485, fail | n/a | none | not significant after FDR control |
| 3-Month Compounded SORA | diff4 | h=1, b=+0.54, t=+1.01, p=0.3130, fail | h=8, b=-0.89, t=-0.26, p=0.7946, fail | n/a | none | not significant after FDR control |
| HDB Resale Price Index | dlog4 | h=1, b=+0.47, t=+0.78, p=0.4342, fail | h=8, b=-2.82, t=-1.08, p=0.2786, fail | yes | none | not significant after FDR control |
| 2-Year Government Bond Yield | diff4 | h=8, b=+1.72, t=+0.58, p=0.5606, fail | h=4, b=+0.77, t=+0.56, p=0.5764, fail | n/a | none | not significant after FDR control |
| Exchange Rate, SGD per USD | dlog4 | not tested | not tested | n/a | none | fewer than 40 observations |

Principal components (robustness check):

| Component | Variance share | Lead test | Strict test |
|---|---|---|---|
| PC1 | 35% | h=1, b=-2.00, t=-4.52, p=0.0000, PASS | h=1, b=-0.64, t=-2.24, p=0.0251, PASS |
| PC2 | 16% | h=8, b=-7.63, t=-2.88, p=0.0040, PASS | h=4, b=-4.82, t=-3.37, p=0.0007, PASS |
| PC3 | 15% | h=8, b=+3.99, t=+1.43, p=0.1535, fail | h=8, b=+4.00, t=+1.42, p=0.1559, fail |

## Principal component loadings

Computed on 13 standardised factors with at least 120 observations, sample 1994 Q2 to 2026 Q2 (n = 129).

| Factor | PC1 | PC2 | PC3 |
|---|---|---|---|
| Consumer Price Index, All Items | -0.25 | +0.23 | -0.23 |
| GDP at Current Market Prices | -0.37 | +0.11 | +0.26 |
| Real GDP, seasonally adjusted | -0.34 | +0.18 | +0.22 |
| HDB Resale Price Index | -0.29 | +0.18 | -0.38 |
| Private Non-Landed Supply Pipeline | -0.36 | -0.05 | -0.26 |
| Total Population | +0.03 | +0.23 | -0.37 |
| 2-Year Government Bond Yield | -0.11 | +0.22 | +0.37 |
| Completed Private Homes (stock growth) | -0.02 | +0.28 | -0.25 |
| Vacant Completed Private Homes | +0.18 | +0.61 | -0.06 |
| Resident Unemployment Rate (SA) | +0.39 | -0.06 | -0.22 |
| Total Unemployment Rate (SA) | +0.39 | -0.07 | -0.21 |
| Private Vacancy Rate (4-quarter change) | +0.21 | +0.53 | +0.08 |
| Private Vacancy Rate (level) | +0.27 | +0.19 | +0.42 |

## Caveats

- Small samples (roughly 80 to 200 quarters) and overlapping horizons; p-values use a normal approximation.
- The best horizon is chosen after looking at four horizons; FDR control covers this but does not remove it.
- Passing the lead test only means the factor moves ahead of the target. It may carry no information beyond the target's own momentum.
- Data are today's vintage, not what was known in real time, and publication lags are ignored.
- Policy changes such as cooling measures create structural breaks that these regressions do not model.
- Predictive association is not causation.
