---
title: "Engineering Take-Home Task: Singapore Housing Factor Workflow"
author: "Zhou Mo"
date: "4 October 2026"
---

# 1. What was built

A command-line workflow that takes a report date and, in one command, downloads six public factors that may predict Singapore private home prices and rents, stores the raw downloads as checksummed snapshots, validates them, computes period changes in the correct unit, and writes a report in which every figure is traced to the published observations behind it.

```
python -m housing_agent run --date 2026-10-04           # the report
python -m housing_agent select-factors --date 2026-10-04  # the evidence behind the factor list
```

No forecasting model is trained. I treated the task as two questions: which few series are worth watching and on what evidence, and how to make the path from the publisher to the report reliable and reproducible. The repository contains the code, 34 tests that run without network, the raw snapshots from a live run on 4 October 2026, the report that run produced, and the factor screening output.

# 2. Factor selection

I started from economic reasoning: housing is moved by financing cost, by demand (income, employment, population) and by supply. That gave a pool of 16 candidate series, all official, published on a fixed schedule and available through one documented API. I then screened the pool against the URA private price and rental indices instead of relying on the reasoning alone.

**Method.** For each factor, target and horizon h of 1, 2, 4 and 8 quarters, two regressions were specified before looking at results. The *lead test* regresses the cumulative h-quarter change in the target on the factor. The *strict test* adds the target's own past growth, with the autoregressive order chosen by BIC, so it asks whether the factor adds anything beyond momentum (the idea behind a Granger causality test). Factors are made stationary by four-quarter log changes (levels) or differences (rates). Standard errors are Newey-West, because overlapping horizons make the errors serially correlated. With about 60 tests per target, significance is judged after Benjamini-Hochberg control of the false discovery rate at 10%. A factor passes only if its sign is the same in both halves of the sample and it is not a near-duplicate (correlation above 0.8) of a stronger passing factor.

**Results.** Samples run from 75 to 201 quarters. All t-statistics below are at a one-quarter horizon.

| Factor | Sale prices | Rents | Sign as expected |
|---|-----|-----|--|
| Private vacancy rate | lead (t = −2.82) | **strict** (t = −3.70 change, −2.57 level) | yes |
| Nominal GDP | lead (t = +3.16)* | **strict** (t = +3.02) | yes |
| HDB resale price index | lead (t = +2.52) | none | yes |
| Resident unemployment rate | none | lead (t = −3.44) | yes |
| Private supply pipeline | lead (t = +2.49) | lead (t = +3.05) | **no** |
| 3-month SORA, CPI, population, bond yields | none | none | |

\* Significant on its own; the screening keeps real GDP (t = +3.54) as the stronger of two near-collinear series.

Three findings shaped the final list.

- **Rents are more predictable than sale prices.** Three factors pass the strict test for rents; none does for sale prices, where four pass the lead test only. Sale prices have strong momentum and are moved by cooling measures that no macro series captures. As a check, the first three principal components of the pool were tested the same way: the second component passes the strict test for sale prices (p = 0.012), so the macro environment as a whole carries information that single series do not.
- **The supply pipeline has the opposite sign to the supply argument.** Developers launch when the market is strong, so at horizons up to two years the pipeline reflects current conditions. I keep it in the report as a monitored series but do not read a direction from it.
- **SORA is not significant, but its history starts in 2005.** With 75 quarters the test has little power. I keep it because it is the reference rate for home loans, and label it as resting on economic reasoning only.

**Final list.** Six factors: vacancy rate, nominal GDP, HDB resale price index, resident unemployment rate, supply pipeline (monitored only) and 3-month SORA. CPI and population were dropped. A factor is read for a market only where the screening supports it, and the report shows the evidence tier (strict, lead or prior) beside every reading. For each factor the report also gives the source and link, definition, unit, observation and update frequency, latest observation, possible time lag and limitations.

# 3. Workflow design

| Stage | What happens | Output kept |
|---|--------|------|
| Fetch | HTTP GET per series, three attempts with backoff for timeouts, 5xx and 429 | Exact response bytes plus URL, retrieval time, SHA-256. Never overwritten |
| Parse and validate | Select the series by number and row text; check frequency and unit against the registry; parse period keys | One validated series, or a precise error |
| Analyse | Latest observation usable at the report date; changes; staleness, gaps, plausible range, revisions | Values, changes, quality flags |
| Report | Render Markdown from the results only (no clock, no network) | `report.md`, `observations.csv`, `manifest.json` |

**Registry.** Everything known about a series (table, row, unit, frequencies, expected lag, sign, evidence, rationale) is in `config/indicators.yaml`. Changing the factor list after the screening was a configuration change, with no change to the pipeline code.

**Units and changes.** Interest rates change in basis points, rates and shares in percentage points, indices and levels in per cent. A change is computed by looking up the exact comparison period; if that period is missing, the change is shown as unavailable instead of comparing against the wrong one.

**Traceability and reproducibility.** For each figure the report prints the calculation with the published values and the snapshot file and checksum, for example: year-on-year −37.8 bp = (1.1863 − 1.5638) × 100. `manifest.json` records which snapshots produced a report, and `--from-manifest` rebuilds it from exactly those files. A test confirms the rebuilt report is byte-identical even after newer, revised data has been downloaded. Running the same request twice adds new snapshots and never alters old ones.

**Where the LLM sits.** No figure comes from a model. The directional readings are computed by rule. With `--llm`, a model writes a short commentary from those readings, and the text is accepted only if every number in it also appears in the computed facts; otherwise it is dropped and the rejection is recorded in the report. I chose this because the value of the report is that its numbers can be trusted. The submitted sample report was produced without an API key and therefore contains no LLM text.

# 4. Reliability

| Situation | Behaviour |
|----|----------|
| Download fails | Retried; then the newest stored snapshot is used and the report says so. Exit code 1 |
| HTTP 200 with an error body or non-JSON | Rejected; falls back as above. The bad payload stays on disk as evidence |
| No data at all for a factor | Shown as UNAVAILABLE; the rest of the report is still produced. Exit code 2 |
| Row numbering shifts at the source | Series is matched on row text as well as number; a mismatch is an error listing the rows returned |
| Unit or frequency changes at the source | Fatal for that factor, since every change would otherwise be silently wrong |
| Missing or non-numeric period | The change that needs it is shown as n/a and logged |
| Stale data | Each factor has a maximum expected age; older data is marked STALE in the summary table |
| Revised history | Each run is compared with the previous snapshot; revised periods are listed |
| Report for a past date | Only periods ended by that date, less the typical publication lag, are used |

# 5. Testing, a failure, and the fix

The 34 tests use payloads with the real API structure and a fake HTTP session. They cover parsing, unit handling, as-of selection, every row of the table above, byte-identical reproduction, the LLM number check, and the econometrics on simulated data where the right answer is known (a planted leading factor passes, noise does not, and a factor that only echoes past growth passes the lead test but fails the strict one).

**Failure on the first live run.** The tests passed, but the first run against the real API returned exit code 2 with SORA unavailable. The SORA row was selected by a keyword pattern, and the live table contains both overnight SORA (series 21) and 3-month compounded SORA (series 23), so two rows matched. The workflow refused to guess and printed the rows it received. The guard did its job: taking the first match would have produced a plausible number from the wrong series. The cause was a test fixture simpler than reality. The fix was to select series 23 with an exact text match, since the compounded rate is the one home loans reference, and to add the second row to the fixture. Both steps are in the commit history.

**A second issue.** The API's `limit` parameter counts cells across all rows of a table, not periods per series, which can truncate history. Requests therefore filter to the one series needed. One candidate, the USD exchange rate, was configured without a series number and came back too short to test; the screening reports it as not tested instead of testing it on a truncated sample.

**Live result, 4 October 2026.** For sale prices three of four factors read as upward pressure (lower vacancy, higher GDP, lower SORA) and the HDB index is flat. For rents two of three read as upward (lower vacancy, higher GDP) and one as downward (higher unemployment). These are directional readings, not a forecast.

# 6. Limitations, and what I would build with two more weeks

- **Screening limits.** Small samples, today's data vintage instead of real-time data, no publication lags, and no treatment of cooling measures. *Next:* add policy dummies for the cooling-measure rounds, and test horizons beyond eight quarters so the supply pipeline can be assessed at the horizon where it should matter.
- **Single upstream API.** A change to the SingStat interface affects all factors at once. *Next:* a second route per series through data.gov.sg or the agency's own API.
- **Back-dated reports are approximate.** True point-in-time data exists only for dates on which a snapshot was taken. *Next:* run on a schedule to build that archive, then repeat the screening on real-time vintages.
- **Coverage.** Private housing only on the target side, and no household income or transaction-volume series. *Next:* add the HDB resale index as a third target and the missing candidates.
- **The LLM check is numeric.** It stops invented figures but not a misleading sentence built from correct ones. *Next:* check each sentence's direction against the computed reading.
- **Not pursued.** ARIMA enters only as the autoregressive benchmark in the strict test. GARCH models volatility, which is not what the task asks about, and a smoothed quarterly index of about 150 observations gives it little to work with.

# 7. Use of AI tools

I used Claude (Anthropic) as a coding assistant throughout, in a chat session with file access to the project folder.

- **Delegated to the AI:** proposing the candidate pool and rationale; writing the Python modules, the tests, the README and the first draft of this report; looking up SingStat table identifiers; implementing the screening regressions; diagnosing the SORA failure from the output I sent it and making the fix; preparing the initial commit history.
- **Done by me:** setting the direction (asking for an econometric screening, choosing the six-factor list from its results, deciding the report layout), running every test and live run on my own machine, reporting the results back, and committing each step.
- **How outputs were checked:** all 34 tests pass on my machine; the live run was repeated after the fix and returned exit code 0; three figures in the sample report were compared with the SingStat website; the update schedule stated for every factor was checked against the agencies' 2026 Q2 release dates (14 July, 24 July, 31 July, 11 August and 23 September); the screening output was read line by line against the factor list.

Commits that include AI-written code carry a `Co-Authored-By` line. I am responsible for the submitted work.
