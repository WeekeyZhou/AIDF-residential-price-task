# Singapore Housing Indicator Report: 2026-10-04

Indicators: 6 (6 current, 0 stale, 0 unavailable). Source: SingStat Table Builder (DOS, MAS, MOM, URA, HDB).

These are directional readings of leading indicators against their own history. They are not a forecast of prices or rents.

## 1. Summary

| Indicator | Latest period | Value | Change on previous period | Change on year ago | Evidence: sale / rent | Pressure on sale prices | Pressure on rents |
|---|---|---|---|---|---|---|---|
| Private Residential Vacancy Rate | 2026 Q2 | 6.35% | +0.18 pp | -0.80 pp | lead / strict | upward | upward |
| GDP at Current Market Prices | 2026 Q2 | S$216,339.3 million | +5.76% * | +12.39% | lead / strict | upward | upward |
| HDB Resale Price Index (2009 Q1 = 100) | 2026 Q2 | 202.800 | -0.29% | -0.05% | lead / not used | little changed | not used |
| Resident Unemployment Rate (seasonally adjusted) | 2026 Q2 | 2.90% | +0.00 pp | +0.20 pp | not used / lead | not used | downward |
| Private Non-Landed Homes in the Supply Pipeline | 2026 Q2 | 51,677 | +7.41% | +6.61% | monitored only | not used | not used |
| 3-Month Compounded SORA | 2026 Aug | 1.19% | +5.1 bp | -37.8 bp | prior / not used | upward | not used |

\* Series is not seasonally adjusted, so this change mostly reflects the season and is not interpreted.

Pressure is read from the year-on-year change and the expected sign of the factor. "Not used" means the factor is not read as a directional signal for that market.

Evidence comes from the factor screening (`python -m housing_agent select-factors`), which tests each factor against the URA private price and rental indices:

- **strict**: passes the strict test (predicts beyond the market's own momentum).
- **lead**: passes the lead test only (leads the market, but adds nothing beyond its momentum).
- **prior**: kept on economic reasoning; not statistically supported in the screening.

## 2. Indicators and traceability

### Private Residential Vacancy Rate

**Why it is included.** Vacancy measures slack in the existing stock. Landlords cut asking rents when units sit empty, so a rising vacancy rate is the most direct leading signal for rents, and a weaker one for sale prices.

**Definition.** Vacant completed private homes divided by all completed private homes, times 100. Computed by this workflow from the two URA series.

**Statistical evidence.** Sale: lead. Rent: strict. The strongest factor in the screening. For rents both the level and the four-quarter change pass the strict test. For sale prices the change passes the lead test.

**Source.** URBAN REDEVELOPMENT AUTHORITY; All Types Private Residential Properties Vacant / All Types Private Residential Properties Available x 100. Unit: Per Cent. Observed: quarterly. Source last updated: 24/07/2026.

| Figure | Calculation | Published observations used |
|---|---|---|
| Value 6.35% | derived | 2026 Q2 = 6.3500 (26961 / 424581 x 100) |
| quarter-on-quarter: +0.18 pp | 6.3500 - 6.1669 | 2026 Q2 = 6.3500 (26961 / 424581 x 100); 2026 Q1 = 6.1669 (26158 / 424165 x 100) |
| year-on-year: -0.80 pp | 6.3500 - 7.1469 | 2026 Q2 = 6.3500 (26961 / 424581 x 100); 2025 Q2 = 7.1469 (30027 / 420142 x 100) |

Snapshot: `stock_vacant/20261004T135334079597Z_ecc817b0.json` (sha256 `ecc817b04074`, retrieved 2026-10-04T13:53:34Z); `stock_available/20261004T135333951062Z_de735fca.json` (sha256 `de735fca9f3f`, retrieved 2026-10-04T13:53:33Z)

### GDP at Current Market Prices

**Why it is included.** Nominal income growth is the main driver of housing affordability and of corporate demand for expatriate housing. The series is not seasonally adjusted, so only the year-on-year change is interpreted.

**Definition.** Quarterly gross domestic product at current prices, S$ million, not seasonally adjusted, published by DOS.

**Statistical evidence.** Sale: lead. Rent: strict. For sale prices nominal GDP is significant on its own in the lead test but is nearly collinear with real GDP, which the screening keeps as the stronger of the two. Nominal GDP is used here because it is the one that passes the strict test for rents.

**Source.** SINGAPORE DEPARTMENT OF STATISTICS; table M015651, series 1 "GDP At Current Market Prices". Unit: Million Dollars. Observed: quarterly, non-seasonally adjusted. Source last updated: 11/08/2026.

| Figure | Calculation | Published observations used |
|---|---|---|
| Value S$216,339.3 million | as published | 2026 Q2 = 216339.3 |
| quarter-on-quarter: +5.76% | (216339.3 / 204554.1 - 1) x 100 | 2026 Q2 = 216339.3; 2026 Q1 = 204554.1 |
| year-on-year: +12.39% | (216339.3 / 192490 - 1) x 100 | 2026 Q2 = 216339.3; 2025 Q2 = 192490 |

Snapshot: `gdp_nominal/20261004T135334238918Z_87b65120.json` (sha256 `87b65120efd9`, retrieved 2026-10-04T13:53:34Z)

### HDB Resale Price Index (2009 Q1 = 100)

**Why it is included.** Most Singapore households live in HDB flats, and many buyers of private homes are HDB owners who sell their flat to upgrade. Rising resale prices raise the equity these upgraders bring to the private market.

**Definition.** Index of resale prices of public (HDB) flats, quarterly, published by HDB.

**Statistical evidence.** Sale: lead. Rent: not used. Passes the lead test for private sale prices. No relationship with private rents was found, so it is not read for the rental market.

**Source.** HOUSING AND DEVELOPMENT BOARD; table M212161, series 1 "HDB Resale Price Index". Unit: Index. Observed: quarterly. Source last updated: 24/07/2026.

| Figure | Calculation | Published observations used |
|---|---|---|
| Value 202.800 | as published | 2026 Q2 = 202.8 |
| quarter-on-quarter: -0.29% | (202.8 / 203.4 - 1) x 100 | 2026 Q2 = 202.8; 2026 Q1 = 203.4 |
| year-on-year: -0.05% | (202.8 / 202.9 - 1) x 100 | 2026 Q2 = 202.8; 2025 Q2 = 202.9 |

Snapshot: `hdb_resale/20261004T135334373834Z_5b818659.json` (sha256 `5b818659642f`, retrieved 2026-10-04T13:53:34Z)

### Resident Unemployment Rate (seasonally adjusted)

**Why it is included.** Rising unemployment weakens household income and tenants' ability to pay, and reduces demand for rental housing from new workers.

**Definition.** Unemployed residents as a share of the resident labour force, end of quarter, seasonally adjusted, published by MOM.

**Statistical evidence.** Sale: not used. Rent: lead. Passes the lead test for rents. For sale prices it is not significant, and after controlling for momentum the estimated sign is positive, which is consistent with prices rebounding after downturns as policy eases. It is therefore not read for the sale market.

**Source.** MINISTRY OF MANPOWER; table M182342, series 2 "Resident Unemployment Rate, (SA)". Unit: Per Cent. Observed: quarterly, seasonally adjusted. Source last updated: 22/09/2026.

| Figure | Calculation | Published observations used |
|---|---|---|
| Value 2.90% | as published | 2026 Q2 = 2.9 |
| quarter-on-quarter: +0.00 pp | 2.9 - 2.9 | 2026 Q2 = 2.9; 2026 Q1 = 2.9 |
| year-on-year: +0.20 pp | 2.9 - 2.7 | 2026 Q2 = 2.9; 2025 Q2 = 2.7 |

Snapshot: `unemployment_resident/20261004T135334484456Z_f35c76ab.json` (sha256 `f35c76ab87ef`, retrieved 2026-10-04T13:53:34Z)

### Private Non-Landed Homes in the Supply Pipeline

**Why it is included.** Units in the pipeline become completed stock within roughly two to four years, so a growing pipeline signals future supply that competes with existing homes for both buyers and tenants.

**Definition.** Uncompleted private apartments and condominium units under construction or planned, end of quarter, published by URA.

**Statistical evidence.** Sale: not used. Rent: not used. Monitored but not read as a directional signal. It passes the lead test for both markets with a POSITIVE sign, the opposite of the supply argument. The likely reason is that developers launch projects when the market is strong, so at short horizons the pipeline reflects current conditions rather than future supply pressure. The supply effect, if any, would appear at horizons longer than the eight quarters tested.

**Source.** URBAN REDEVELOPMENT AUTHORITY; table M400391, series 2 "Total Non-Landed Properties". Unit: Number Of Units. Observed: quarterly. Source last updated: 24/07/2026.

| Figure | Calculation | Published observations used |
|---|---|---|
| Value 51,677 | as published | 2026 Q2 = 51677 |
| quarter-on-quarter: +7.41% | (51677 / 48111 - 1) x 100 | 2026 Q2 = 51677; 2026 Q1 = 48111 |
| year-on-year: +6.61% | (51677 / 48474 - 1) x 100 | 2026 Q2 = 51677; 2025 Q2 = 48474 |

Snapshot: `pipeline_nonlanded/20261004T135334590277Z_317f8753.json` (sha256 `317f875344ed`, retrieved 2026-10-04T13:53:34Z)

### 3-Month Compounded SORA

**Why it is included.** Three-month compounded SORA is the reference rate for most floating-rate Singapore home loans, so it moves monthly instalments and the amount buyers can borrow under the Total Debt Servicing Ratio. The effect on rents is ambiguous, so it is not read for the rental market.

**Definition.** Singapore Overnight Rate Average compounded over the preceding three months, end of month, published by MAS. SORA is the volume-weighted average rate of unsecured overnight interbank SGD transactions.

**Statistical evidence.** Sale: prior. Rent: not used. Not significant in the screening, but the series only starts in 2005 (about 75 quarters), so the test has little power. It is kept because it is the reference rate for home loans, and is labelled as resting on economic reasoning only.

**Source.** MONETARY AUTHORITY OF SINGAPORE; table M700071, series 23 "Compounded Singapore Overnight Rate Average (SORA) - 3 Month". Unit: Per Cent Per Annum. Observed: monthly. Source last updated: 14/09/2026.

| Figure | Calculation | Published observations used |
|---|---|---|
| Value 1.19% | as published | 2026 Aug = 1.1863 |
| month-on-month: +5.1 bp | (1.1863 - 1.1354) x 100 | 2026 Aug = 1.1863; 2026 Jul = 1.1354 |
| year-on-year: -37.8 bp | (1.1863 - 1.5638) x 100 | 2026 Aug = 1.1863; 2025 Aug = 1.5638 |

Snapshot: `sora/20261004T135334732769Z_04768d2d.json` (sha256 `04768d2d8a07`, retrieved 2026-10-04T13:53:34Z)

## 3. Data quality

No issues: all downloads succeeded, no gaps, no stale series, no revisions since the previous snapshot.

Figures reflect the data vintage of the snapshots listed above. Past values may have been revised by the publisher since they were first released.
