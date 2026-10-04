"""Render the Markdown report. Pure function of its inputs: no clock, no network."""
from __future__ import annotations

from datetime import date

from .analyse import Result
from .config import FREQUENCIES
from .formatting import fmt_change, fmt_value, formula
from .narrative import DISCLAIMER, EVIDENCE, MARKETS


def _snap_ref(res: Result) -> str:
    return "; ".join(f"`{s.path.parent.name}/{s.path.name}` (sha256 `{s.sha256[:12]}`, retrieved {s.retrieved_at[:19]}Z)"
                     for s in res.snapshots)


def _evidence(res: Result) -> str:
    ev = res.indicator.evidence
    if not ev:
        return "monitored only" if res.indicator.evidence_note else "n/a"
    return f"{ev.get('sale', 'not used')} / {ev.get('rent', 'not used')}"


def render(report_date: date, results: list[Result], facts: dict, commentary: dict) -> str:
    shown = [r for r in results if r.indicator.report]
    counts = {s: sum(r.status == s for r in shown) for s in ("OK", "STALE", "UNAVAILABLE")}
    L = [f"# Singapore Housing Indicator Report: {report_date.isoformat()}", ""]
    L += [f"Indicators: {len(shown)} ({counts['OK']} current, {counts['STALE']} stale, "
          f"{counts['UNAVAILABLE']} unavailable). Source: SingStat Table Builder (DOS, MAS, MOM, URA, HDB).",
          "", DISCLAIMER, ""]

    signal = {m: {r["id"]: r["direction"] for r in facts[m]["readings"]} for m in MARKETS}
    words = {1: "upward", -1: "downward", 0: "little changed"}

    def pressure(res: Result, market: str) -> str:
        if not res.indicator.effect.get(market):
            return "not used"
        return words[signal[market][res.indicator.id]] if res.indicator.id in signal[market] else "n/a"

    L += ["## 1. Summary", "",
          "| Indicator | Latest period | Value | Change on previous period | Change on year ago | "
          "Evidence: sale / rent | Pressure on sale prices | Pressure on rents |",
          "|---|---|---|---|---|---|---|---|"]
    for r in shown:
        tail = f"{_evidence(r)} | {pressure(r, 'sale')} | {pressure(r, 'rent')} |"
        if r.status == "UNAVAILABLE":
            L.append(f"| {r.indicator.name} | UNAVAILABLE | n/a | n/a | n/a | {tail}")
            continue
        cells = []
        for c in r.comparisons:
            cell = fmt_change(c.unit, c.change)
            if c.note and c.change is not None:
                cell += " *"
            cells.append(cell)
        if r.indicator.frequency == "A":
            cells = ["n/a (annual)", cells[0]]
        period = r.period.label + (" (STALE)" if r.status == "STALE" else "")
        L.append(f"| {r.indicator.name} | {period} | {fmt_value(r.series.unit, r.value)} | "
                 f"{cells[0]} | {cells[1]} | {tail}")
    L += ["", "\\* Series is not seasonally adjusted, so this change mostly reflects the season and is not interpreted.", "",
          "Pressure is read from the year-on-year change and the expected sign of the factor. "
          "\"Not used\" means the factor is not read as a directional signal for that market.", ""]
    if any(r.indicator.evidence for r in shown):
        L += ["Evidence comes from the factor screening (`python -m housing_agent select-factors`), which tests "
              "each factor against the URA private price and rental indices:", ""]
        L += [f"- **{tier}**: {text}." for tier, text in EVIDENCE.items()]
        L += [""]

    section = 2
    if any(c["mode"] == "llm" for c in commentary.values()):
        L += [f"## {section}. Commentary", ""]
        for market, title in (("sale", "Sale market"), ("rent", "Rental market")):
            if commentary[market]["mode"] == "llm":
                L += [f"**{title}.** {commentary[market]['summary']}", ""]
        L += ["_Written by an LLM from the readings in the summary table. Every number in it was checked "
              "against the computed figures._", ""]
        section += 1

    L += [f"## {section}. Indicators and traceability", ""]
    for r in shown:
        ind = r.indicator
        L += [f"### {ind.name}", "", f"**Why it is included.** {ind.rationale.strip()}", "",
              f"**Definition.** {ind.definition.strip()}", ""]
        if ind.evidence or ind.evidence_note:
            L += [f"**Statistical evidence.** Sale: {ind.evidence.get('sale', 'not used')}. "
                  f"Rent: {ind.evidence.get('rent', 'not used')}. {ind.evidence_note.strip()}", ""]
        if r.status == "UNAVAILABLE":
            L += [f"**Unavailable:** {r.error}", ""]
            continue
        s = r.series
        src = f"table {ind.table}, series {s.series_no} \"{s.row_text}\"" if ind.table else s.row_text
        L += [f"**Source.** {s.datasource}; {src}. Unit: {s.unit}. Observed: {FREQUENCIES[ind.frequency].lower()}"
              f"{', ' + s.adjustment.lower() if s.adjustment else ''}. "
              f"Source last updated: {s.data_last_updated or 'n/a'}.", "",
              "| Figure | Calculation | Published observations used |", "|---|---|---|",
              f"| Value {fmt_value(s.unit, r.value)} | {'derived' if ind.derived else 'as published'} | "
              f"{r.period.label} = {r.raw} |"]
        cur = f"{r.value:.4f}" if ind.derived else r.raw
        for c in r.comparisons:
            if c.change is None:
                L.append(f"| {c.label}: n/a | not computed | {c.note} |")
            else:
                L.append(f"| {c.label}: {fmt_change(c.unit, c.change)} | "
                         f"{formula(ind.unit_kind, cur, f'{c.value:.4f}' if ind.derived else c.raw)} | "
                         f"{r.period.label} = {r.raw}; {c.period.label} = {c.raw} |")
        L += ["", f"Snapshot: {_snap_ref(r)}", ""]

    L += [f"## {section + 1}. Data quality", ""]
    rows = [f"- **commentary ({m})**: {c['note']}" for m, c in commentary.items() if c["note"]]
    for r in results:
        if r.status == "UNAVAILABLE":
            rows.append(f"- **{r.indicator.id}** UNAVAILABLE: {r.error}")
        rows += [f"- **{r.indicator.id}** {level} `{code}`: {msg}" for level, code, msg in r.issues]
        for period, old, new in r.revisions[-8:]:
            rows.append(f"- **{r.indicator.id}** revision: {period.label} changed from {old:g} to {new:g} "
                        f"since the previous snapshot")
        if len(r.revisions) > 8:
            rows.append(f"- **{r.indicator.id}** {len(r.revisions) - 8} earlier revised periods not listed")
    L += rows or ["No issues: all downloads succeeded, no gaps, no stale series, no revisions since the previous snapshot."]
    L += ["", "Figures reflect the data vintage of the snapshots listed above. Past values may have been "
              "revised by the publisher since they were first released.", ""]
    return "\n".join(L)
