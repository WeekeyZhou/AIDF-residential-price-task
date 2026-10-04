"""Orchestration: one function that goes from a report date to a report."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime
from pathlib import Path

from . import __version__
from .analyse import Result, analyse, find_revisions
from .config import Config, Indicator
from .fetch import FetchError, Snapshot, download, find_snapshot, list_snapshots
from .narrative import build_facts, write_commentary
from .parse import ParseError, derive_ratio_pct, parse_series
from .report import render


def _retrieved_date(snap: Snapshot) -> date:
    return datetime.fromisoformat(snap.retrieved_at).date()


def _load(ind: Indicator, cfg: Config, raw_root: Path, mode: str, pinned: dict, session) -> tuple:
    """Return (snapshot, series, origin, issues). Raises FetchError/ParseError if nothing usable."""
    issues = []
    if mode == "manifest":
        snap = find_snapshot(raw_root, ind.id, pinned[ind.id]["sha256"], pinned[ind.id].get("file", ""))
        return snap, parse_series(snap.read(), ind), "stored snapshot pinned by manifest", issues

    stored = list_snapshots(raw_root, ind.id)
    if mode == "live":
        try:
            snap = download(cfg, ind, raw_root, session=session)
            return snap, parse_series(snap.read(), ind), "live download", issues
        except FetchError as exc:
            issues.append(("error", "download_failed", str(exc)))
        except ParseError as exc:
            # The bad payload stays on disk as evidence but must not be reused.
            issues.append(("error", "bad_payload", f"downloaded payload rejected: {exc}"))

    # Offline mode, or live mode after a failure: newest stored snapshot that parses.
    for snap in reversed(stored):
        try:
            series = parse_series(snap.read(), ind)
        except (ParseError, FetchError):
            continue
        if mode == "offline":
            return snap, series, "stored snapshot", issues
        issues.append(("warning", "fallback", f"using the earlier snapshot retrieved {snap.retrieved_at}"))
        return snap, series, "FALLBACK to stored snapshot", issues
    detail = "; ".join(msg for _, _, msg in issues) or "no stored snapshot"
    raise FetchError(f"no usable data: {detail}")


def _previous_series(ind: Indicator, raw_root: Path, current: Snapshot):
    older = [s for s in list_snapshots(raw_root, ind.id)
             if s.retrieved_at < current.retrieved_at and s.sha256 != current.sha256]  # ISO UTC strings sort by time
    for snap in reversed(older):
        try:
            return parse_series(snap.read(), ind)
        except (ParseError, FetchError):
            continue
    return None


def run(cfg: Config, report_date: date, raw_root: Path, out_root: Path, mode: str = "live",
        manifest_path: Path | None = None, llm=None, session=None, config_path: Path | None = None):
    """Run the workflow. Returns (output folder, results, exit code).

    Exit code: 0 all indicators current; 1 report produced with stale or
    fallback data; 2 report produced but at least one indicator unavailable.
    """
    pinned = {}
    if manifest_path:
        mode = "manifest"
        pinned = json.loads(Path(manifest_path).read_text(encoding="utf-8"))["snapshots"]

    results: dict[str, Result] = {}
    for ind in cfg.indicators:
        if ind.derived:
            continue
        try:
            snap, series, origin, issues = _load(ind, cfg, raw_root, mode, pinned, session)
        except (FetchError, ParseError, KeyError) as exc:
            results[ind.id] = Result(indicator=ind, status="UNAVAILABLE", error=str(exc))
            continue
        res = analyse(ind, series, report_date, _retrieved_date(snap))
        res.issues = issues + res.issues
        res.snapshots, res.origin = [snap], origin
        previous = _previous_series(ind, raw_root, snap)
        if previous:
            res.revisions = find_revisions(previous, series)
        results[ind.id] = res

    for ind in cfg.indicators:
        if not ind.derived:
            continue
        num, den = results[ind.derived["numerator"]], results[ind.derived["denominator"]]
        if num.series is None or den.series is None:
            results[ind.id] = Result(indicator=ind, status="UNAVAILABLE",
                                     error="an input series is unavailable")
            continue
        try:
            series = derive_ratio_pct(ind, num.series, den.series)
        except ParseError as exc:
            results[ind.id] = Result(indicator=ind, status="UNAVAILABLE", error=str(exc))
            continue
        snaps = num.snapshots + den.snapshots
        res = analyse(ind, series, report_date, min(_retrieved_date(s) for s in snaps))
        res.snapshots = snaps
        res.origin = f"derived from {num.indicator.id} ({num.origin}) and {den.indicator.id} ({den.origin})"
        results[ind.id] = res

    ordered = [results[ind.id] for ind in cfg.indicators]
    shown = [r for r in ordered if r.indicator.report]
    facts = build_facts(shown)
    commentary = write_commentary(facts, llm=llm)

    out_dir = out_root / report_date.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.md").write_text(render(report_date, ordered, facts, commentary), encoding="utf-8")
    _write_observations(out_dir / "observations.csv", ordered)
    _write_manifest(out_dir / "manifest.json", report_date, mode, ordered, commentary, config_path)

    statuses = {r.status for r in shown}
    degraded = "STALE" in statuses or any("FALLBACK" in r.origin for r in ordered)
    code = 2 if "UNAVAILABLE" in statuses else 1 if degraded else 0
    return out_dir, ordered, code


def _write_observations(path: Path, results: list[Result]) -> None:
    """Normalised long table of every observation the report could draw on."""
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["indicator_id", "period", "period_end", "value", "published_value", "unit",
                    "frequency", "snapshot_sha256"])
        for r in results:
            if r.series is None:
                continue
            sha = "+".join(s.sha256[:12] for s in r.snapshots)
            for p in sorted(r.series.obs):
                w.writerow([r.indicator.id, p.label, p.end_date(r.indicator.annual_ref_month).isoformat(),
                            repr(r.series.obs[p]), r.series.raw[p], r.series.unit, r.indicator.frequency, sha])


def _write_manifest(path: Path, report_date: date, mode: str, results: list[Result],
                    commentary: dict, config_path: Path | None) -> None:
    manifest = {
        "report_date": report_date.isoformat(),
        "mode": mode,
        "code_version": __version__,
        "config_sha256": hashlib.sha256(Path(config_path).read_bytes()).hexdigest() if config_path else None,
        "commentary_mode": {m: c["mode"] for m, c in commentary.items()},
        "status": {r.indicator.id: r.status for r in results},
        "snapshots": {r.indicator.id: {"file": f"{r.indicator.id}/{r.snapshots[0].path.name}",
                                       "sha256": r.snapshots[0].sha256,
                                       "retrieved_at": r.snapshots[0].retrieved_at,
                                       "url": r.snapshots[0].url}
                      for r in results if r.snapshots and not r.indicator.derived},
    }
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
