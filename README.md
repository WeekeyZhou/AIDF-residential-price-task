# Singapore Housing Indicator Workflow

One command takes a report date, downloads a small set of public macro
indicators that lead Singapore home prices and rents, keeps the raw downloads
as checksummed snapshots, computes period changes, and writes a report in
which every figure is traced back to the published observations behind it.

No forecasting model is trained. The aim is a small indicator set chosen with
judgement, and a data path that is reliable and reproducible.

## Run it

```
pip install -r requirements.txt
python -m housing_agent run --date 2026-10-04
```

Output goes to `output/<date>/`:

| File | Content |
|---|---|
| `report.md` | The report: summary table, readings for the sale and rental markets, per-indicator rationale and traceability, data-quality log |
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
python -m housing_agent list-series M700071                      # inspect the rows of a source table
python -m pytest                                                 # 22 tests, no network needed
```

Exit code: `0` all indicators current; `1` report written using stale or
fallback data; `2` report written but an indicator is unavailable. A report is
always written, so a scheduler can alert on the code and a reader still sees
what is missing.

## Indicators

All series come from the SingStat Table Builder API, which republishes the
official DOS, MAS, MOM and URA series with consistent metadata. The registry
is `config/indicators.yaml`; adding an indicator is a config change.

| Indicator | Publisher, table | Observed | Change shown in | Sale | Rent | Why |
|---|---|---|---|---|---|---|
| SORA | MAS, M700071 | Monthly | basis points | − | not used | Mortgage benchmark: sets instalments and borrowing capacity |
| CPI, All Items | DOS, M213751 | Monthly | % | + | + | Nominal anchor for rents and building costs; drives MAS policy |
| Nominal GDP | DOS, M015651 | Quarterly | % (year-on-year only) | + | + | Income growth and corporate housing demand |
| Resident unemployment rate, SA | MOM, M182342 | Quarterly | percentage points | − | − | Income security of the households that buy |
| Total population | DOS, M810001 | Annual (end-June) | % | + | + | Basic demand; non-resident inflows mostly rent |
| Private non-landed supply pipeline | URA, M400391 | Quarterly | % | − | − | Completions two to four years ahead |
| Private residential vacancy rate | derived from URA, M400841 | Quarterly | percentage points | − | − | Slack in the existing stock; the most direct rental signal |

The sign is the expected pressure on prices or rents when the indicator rises.
The full reasoning for each is in the config file and is printed in the report.

## How it works

```
config/indicators.yaml          what to fetch, units, expected lags, rationale
housing_agent/fetch.py          download with retry -> immutable snapshot + checksum
housing_agent/parse.py          payload -> one validated series (or a precise error)
housing_agent/analyse.py        as-of selection, changes, staleness, gaps, revisions
housing_agent/narrative.py      rule-based readings; optional LLM paragraph with a number check
housing_agent/report.py         Markdown report (pure function: no clock, no network)
housing_agent/pipeline.py       orchestration, fallback, manifest, exit code
housing_agent/cli.py            command line
```

### Where the agent/LLM sits

The numbers are never produced by a model. Directional readings are computed
by rule from the configured sign of each indicator. With `--llm`, a model
rewrites those readings into one paragraph per market, and the text is accepted
only if every number in it also appears in the computed facts; otherwise the
rule-based paragraph is used and the rejection is noted in the report. Without
an API key the workflow runs fully deterministically.

### Reliability

| Situation | Behaviour |
|---|---|
| Download fails (timeout, 5xx, 429) | Retried three times with backoff. Then the newest stored snapshot is used and the report says so (`download_failed`, `fallback`), exit code 1 |
| HTTP 200 with an error body, or non-JSON | Rejected (`bad_payload`); falls back as above |
| No data at all for an indicator | Marked UNAVAILABLE in the report, the rest is still produced, exit code 2 |
| Publisher inserts a row and series numbers shift | Row is matched on its text as well as its number; a mismatch is an error listing the rows returned |
| Unit or frequency changes at the source | Fatal for that indicator: a silent unit change would corrupt every figure |
| A period is missing or non-numeric | The change that needs it is shown as n/a. Changes are looked up by exact period, never by "previous row" |
| Newest observation older than the indicator's expected lag | Flagged STALE in the summary table and data-quality section |
| Value outside a plausible range | Warning (`out_of_range`) |
| Publisher revises history | Compared with the previous snapshot; revised periods are listed |
| Report for a past date | Only periods ended by that date, less the typical publication lag, are used |
| Reproducing a report later | `--from-manifest` uses the exact snapshots, verified by checksum |

## Sample output

`output/` contains a sample report produced by a live run, and `data/raw/`
the snapshots behind it, so `--from-manifest` can recreate it without network.

## Limitations

- Single upstream API. If SingStat changes its interface, all indicators are affected at once; stored snapshots keep reports reproducible but not current.
- A back-dated report uses today's vintage of the data with a publication-lag rule. It is not a true point-in-time vintage unless a snapshot from that date exists.
- Directional signs are fixed judgements, not estimated relationships, and lags differ by indicator.
- No public-housing (HDB) supply series and no household-income series are included.

## Use of AI tools

This project was built with Claude (Anthropic) as a coding assistant; commits
made with it carry a `Co-Authored-By` line. See the summary report for what
was delegated and how the output was checked.
