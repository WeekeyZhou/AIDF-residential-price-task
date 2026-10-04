"""Commentary for the report.

The directional reading of each indicator is computed by rule. An LLM, when
enabled, only rewrites those readings as prose, and its text is accepted only
if every number in it also appears in the computed facts. Otherwise the
deterministic text is used. The model never supplies a figure.
"""
from __future__ import annotations

import os
import re

import requests

from .analyse import Result
from .formatting import fmt_change, fmt_value

FLAT = {"%": 0.1, "bp": 5.0, "pp": 0.05}  # smaller moves are "little changed"
MARKETS = {"sale": "sale prices", "rent": "rents"}
EVIDENCE = {
    "strict": "passes the strict test (predicts beyond the market's own momentum)",
    "lead": "passes the lead test only (leads the market, but adds nothing beyond its momentum)",
    "prior": "kept on economic reasoning; not statistically supported in the screening",
}
DISCLAIMER = ("These are directional readings of leading indicators against their own "
              "history. They are not a forecast of prices or rents.")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def reading(res: Result, market: str) -> dict | None:
    """Directional reading of one indicator for one market, or None."""
    effect = res.indicator.effect.get(market, 0)
    comp = res.comparison("year-on-year")
    if res.status == "UNAVAILABLE" or not effect or comp is None or comp.change is None:
        return None
    if abs(comp.change) < FLAT[comp.unit]:
        direction = 0
    else:
        direction = effect if comp.change > 0 else -effect
    words = {1: f"upward pressure on {MARKETS[market]}",
             -1: f"downward pressure on {MARKETS[market]}",
             0: "little changed"}
    text = (f"{res.indicator.name} was {fmt_value(res.series.unit, res.value)} in {res.period.label}, "
            f"{fmt_change(comp.unit, comp.change)} year-on-year: {words[direction]}.")
    tier = res.indicator.evidence.get(market)
    if tier:
        text += f" [Evidence: {tier}]"
    if res.status == "STALE":
        text += " (Stale data.)"
    return {"id": res.indicator.id, "direction": direction, "text": text}


def build_facts(results: list[Result]) -> dict:
    facts = {}
    for market in MARKETS:
        readings = [r for r in (reading(res, market) for res in results) if r]
        facts[market] = {
            "readings": readings,
            "up": sum(r["direction"] == 1 for r in readings),
            "down": sum(r["direction"] == -1 for r in readings),
            "flat": sum(r["direction"] == 0 for r in readings),
        }
    return facts


def template_summary(market: str, block: dict) -> str:
    n = len(block["readings"])
    if not n:
        return f"No indicator could be read for {MARKETS[market]} at this report date."
    return (f"Of {n} indicators read for {MARKETS[market]}, {block['up']} point to upward pressure, "
            f"{block['down']} to downward pressure and {block['flat']} are little changed.")


def numbers_in(text: str) -> set:
    return {round(float(m.replace(",", "")), 6) for m in _NUMBER.findall(text)}


def ungrounded_numbers(text: str, facts: dict) -> set:
    """Numbers in text that do not appear anywhere in the computed facts."""
    allowed = set()
    for market, block in facts.items():
        allowed |= numbers_in(template_summary(market, block))
        for r in block["readings"]:
            allowed |= numbers_in(r["text"])
    return numbers_in(text) - allowed


def call_anthropic(prompt: str) -> str:
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
        json={"model": os.environ.get("HOUSING_AGENT_MODEL", "claude-sonnet-5-5"), "max_tokens": 600,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=60,
    )
    resp.raise_for_status()
    return "".join(b.get("text", "") for b in resp.json()["content"]).strip()


def build_prompt(market: str, block: dict) -> str:
    lines = "\n".join(f"- {r['text']}" for r in block["readings"])
    return (f"You are writing one paragraph for a Singapore housing indicator report about {MARKETS[market]}.\n"
            f"Facts (computed, authoritative):\n{template_summary(market, block)}\n{lines}\n\n"
            "Write at most 110 words of plain prose explaining what these readings jointly suggest and "
            "which matter most. Use only numbers that appear in the facts, exactly as written. "
            "Do not forecast any price or rent level or change. Do not add facts.")


def write_commentary(facts: dict, llm=None) -> dict:
    """Return {market: {'summary', 'mode', 'note'}}. llm is a callable(prompt) -> str or None."""
    out = {}
    for market, block in facts.items():
        summary, mode, note = template_summary(market, block), "template", ""
        if llm and block["readings"]:
            try:
                text = llm(build_prompt(market, block))
            except Exception as exc:  # network, auth, bad response: never fail the report
                note = f"LLM call failed ({type(exc).__name__}); deterministic text used."
            else:
                bad = ungrounded_numbers(text, facts)
                if not text.strip():
                    note = "LLM returned no text; deterministic text used."
                elif bad:
                    note = (f"LLM text rejected: it contained numbers not in the computed facts "
                            f"({', '.join(f'{b:g}' for b in sorted(bad))}); deterministic text used.")
                else:
                    summary, mode = text.strip(), "llm"
        out[market] = {"summary": summary, "mode": mode, "note": note}
    return out
