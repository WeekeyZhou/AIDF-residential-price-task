# Singapore Housing Factor Workflow

One command takes a report date, downloads six public factors that may
predict Singapore private home prices and rents, keeps the raw downloads
as checksummed snapshots, computes period changes, and writes a report in
which every figure is traced back to the published observations behind it.

No forecasting model is trained. The aim is a small factor set chosen with
judgement and checked against the data, and a data path that is reliable and
reproducible. `docs/Summary Report.pdf` is the write-up.

## Run it

```
pip install -r requirements.txt
python -m housing_agent run --date 2026-10-04
```

Output goes to `output/<date>/`:

| File | Content |
|---|---|
| `report.md` | The report: summary table with the directional reading and evidence tier of each factor; per-factor source, definition, unit, frequencies, time lag, limitations and traceability; data-quality log |
| `observations.csv` | Every validated observation in one long table (indicator, period, period end, value, published value, unit, snapshot checksum) |
| `manifest.json` | Exactly which raw snapshots (file, SHA-256, retrieval time, URL) produced this report |

Raw downloads go to `data/raw/<indicator>/<UTC time>_<sha8>.json` with a
`.meta.json` beside each. They are never modified or overwritten.

Other commands:

```
python -m housing_agent run --date 2026-10-04 --offline          # no network, newest stored snapshots
python -m housing_agent run --date 2026-10-04 --from-manifest output/2026-10-04/manifest.json
                                                                # recreate a past report byte for byte
python -m housing_agent run --date 2026-10-04 --llm              # LLM-written commentary (needs ANTHROPIC_API_KEY)
python -m housing_agent select-factors --date 2026-10-04         # screen the candidate pool (see below)
python -m housing_agent select-factors --date 2026-10-04 --offline
python -m housing_agent list-series M700071                      # inspect the rows of a source table
python -m pytest                                                 # 34 tests, no network needed
```

Exit code: `0` all factors current; `1` report written using stale or
fallback data; `2` report written but a factor is unavailable. A report is
always written, so a scheduler can alert on the code and a reader still sees
what is missing.

## Factors

All series come from the SingStat Table Builder API, which republishes the
official MAS, DOS, MOM, URA and HDB series with consistent metadata. The
registry is `config/indicators.yaml`; changing the factor list is a config
change.

| Factor | Publisher, table | Observed | Change shown in | Read for sale prices | Read for rents |
|---|---|---|---|---|---|
| Private residential vacancy rate | derived from URA, M400841 | Quarterly | percentage points | − (lead) | − (strict) |
| Nominal GDP | DOS, M015651 | Quarterly | % (year-on-year only) | + (lead) | + (strict) |
| HDB resale price index | HDB, M212161 | Quarterly | % | + (lead) | not used |
| Resident unemployment rate, SA | MOM, M182342 | Quarterly | percentage points | not used | − (lead) |
| Private non-landed supply pipeline | URA, M400391 | Quarterly | % | monitored only | monitored only |
| 3-month compounded SORA | MAS, M700071 | Monthly | basis points | − (prior) | not used |

The sign is the expected pressure when the factor rises. The word in brackets
is the evidence tier from the screening below. A factor is read for a market
only where it has a tier.

## Factor selection

`select-factors` screens the 16 candidates in `config/candidates.yaml` against
the URA private price and rental indices and writes
`output/selection/<date>/factor_selection.md` and `factor_tests.csv`.

- **Lead test:** does the factor lead the cumulative change in the target over
  the next 1, 2, 4 or 8 quarters?
- **Strict test:** does it still do so after controlling for the target's own
  past growth (autoregressive order chosen by BIC)?
- Newey-West standard errors; Benjamini-Hochberg control of the false discovery
  rate at 10% across all factor x horizon tests for a target; the sign must be
  the same in both halves of the sample; near-duplicates are pruned.
- Evidence tiers: **strict** passes the strict test, **lead** passes the lead
  test only, **prior** is kept on economic reasoning without statistical support.
- The same tests are run on the first three principal components of the pool
  as a robustness check.

This is a screening exercise on small samples, not a forecasting model. Its
caveats are listed at the end of the selection report.

## How it works

```
config/indicators.yaml          the six factors: what to fetch, units, lags, sign, evidence, rationale
config/candidates.yaml          the 16-candidate pool and the two targets used for screening
housing_agent/fetch.py          download with retry -> immutable snapshot + checksum
housing_agent/parse.py          payload -> one validated series (or a precise error)
housing_agent/analyse.py        as-of selection, changes, staleness, gaps, revisions
housing_agent/narrative.py      rule-based readings; optional LLM paragraph with a number check
housing_agent/selection.py      factor screening: predictive regressions, HAC errors, FDR, PCA
housing_agent/report.py         Markdown report (pure function: no clock, no network)
housing_agent/pipeline.py       orchestration, fallback, manifest, exit code
housing_agent/cli.py            command line
```

### Where the agent/LLM sits

The numbers are never produced by a model. Directional readings are computed
by rule from the configured sign of each factor. With `--llm`, a model
writes a short commentary from those readings, and the text is accepted only if
every number in it also appears in the computed facts; otherwise it is dropped
and the rejection is noted in the report. Without
an API key the workflow runs fully deterministically.

### Reliability

| Situation | Behaviour |
|---|---|
| Download fails (timeout, 5xx, 429) | Retried three times with backoff. Then the newest stored snapshot is used and the report says so (`download_failed`, `fallback`), exit code 1 |
| HTTP 200 with an error body, or non-JSON | Rejected (`bad_payload`); falls back as above |
| No data at all for a factor | Marked UNAVAILABLE in the report, the rest is still produced, exit code 2 |
| Publisher inserts a row and series numbers shift | Row is matched on its text as well as its number; a mismatch is an error listing the rows returned |
| Unit or frequency changes at the source | Fatal for that factor: a silent unit change would corrupt every figure |
| A period is missing or non-numeric | The change that needs it is shown as n/a. Changes are looked up by exact period, never by "previous row" |
| Newest observation older than the factor's expected lag | Marked STALE in the summary table and logged in the data-quality section |
| Value outside a plausible range | Warning (`out_of_range`) |
| Publisher revises history | Compared with the previous snapshot; revised periods are listed |
| Report for a past date | Only periods ended by that date, less the typical publication lag, are used |
| Reproducing a report later | `--from-manifest` uses the exact snapshots, verified by checksum |

## Sample output

`output/2026-10-04/` contains a sample report produced by a live run,
`output/selection/2026-10-04/` the factor screening from the same day, and
`data/raw/` the snapshots behind both, so `--from-manifest` and
`select-factors --offline` can recreate them without network.

## Limitations

- Single upstream API. If SingStat changes its interface, all factors are affected at once; stored snapshots keep reports reproducible but not current.
- A back-dated report uses today's vintage of the data with a publication-lag rule. It is not a true point-in-time vintage unless a snapshot from that date exists.
- The screening uses small samples and today's data vintage, ignores publication lags, and does not model cooling measures. Passing the lead test only means a factor moves ahead of the target.
- Targets are private housing only, and no household-income series is included.

## Use of AI tools

This project was built with Claude (Anthropic) as a coding assistant; commits
made with it carry a `Co-Authored-By` line. See the summary report for what
was delegated and how the output was checked.
