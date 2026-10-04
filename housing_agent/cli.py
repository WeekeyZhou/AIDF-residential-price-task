"""Command line entry point:  python -m housing_agent run --date 2026-10-04"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import requests

from .config import load_config
from .fetch import USER_AGENT
from .narrative import call_anthropic
from .pipeline import run


def _cmd_run(args) -> int:
    cfg = load_config(args.config)
    llm = None
    if args.llm:
        if os.environ.get("ANTHROPIC_API_KEY"):
            llm = call_anthropic
        else:
            print("--llm given but ANTHROPIC_API_KEY is not set; using deterministic commentary.", file=sys.stderr)
    mode = "offline" if args.offline else "live"
    out_dir, results, code = run(cfg, args.date, Path(args.raw), Path(args.out), mode=mode,
                                 manifest_path=args.from_manifest, llm=llm, config_path=args.config)
    for r in results:
        latest = r.period.label if r.period else "-"
        print(f"{r.status:<12}{r.indicator.id:<24}{latest:<10}{r.origin or r.error}")
    print(f"\nReport: {out_dir / 'report.md'}  (exit code {code})")
    return code


def _cmd_list_series(args) -> int:
    """Print the rows of a SingStat table, to find or check a series."""
    cfg = load_config(args.config)
    resp = requests.get(f"{cfg.base_url}/{args.table}", params={"limit": cfg.limit, "sortBy": "key desc"},
                        timeout=30, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    resp.raise_for_status()
    data = json.loads(resp.content)["Data"]
    print(f"{data['id']}: {data['title']} [{data['frequency']}] last updated {data['dataLastUpdated']}")
    for row in data["row"]:
        cols = row.get("columns") or [{}]
        print(f"  {row['seriesNo']:<8}{row['rowText']} [{row['uoM']}] "
              f"latest {cols[0].get('key')} = {cols[0].get('value')} ({len(cols)} obs returned)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="housing_agent", description=__doc__)
    parser.add_argument("--config", default="config/indicators.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="download, validate, compute and write the report")
    p.add_argument("--date", type=date.fromisoformat, default=date.today(), help="report date, YYYY-MM-DD")
    p.add_argument("--raw", default="data/raw", help="folder for raw snapshots")
    p.add_argument("--out", default="output", help="folder for reports")
    p.add_argument("--offline", action="store_true", help="use the newest stored snapshots; no network")
    p.add_argument("--from-manifest", help="re-create a report from the exact snapshots in a manifest.json")
    p.add_argument("--llm", action="store_true", help="let an LLM write the commentary paragraphs (checked)")
    p.set_defaults(func=_cmd_run)

    p = sub.add_parser("list-series", help="show the rows of a SingStat table")
    p.add_argument("table")
    p.set_defaults(func=_cmd_list_series)

    args = parser.parse_args(argv)
    return args.func(args)
