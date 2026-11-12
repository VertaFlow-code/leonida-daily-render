#!/usr/bin/env python3
"""Variety + sourcing guardrail for Leonida Daily manifests.

Fails the render (exit 1) when a Short looks templated or unsourced, which is
both a YouTube repetitive-content risk and a quality problem.

Rules
  - no layout used 3 times in a row
  - no single layout above 50% of card scenes (when 4+ cards)
  - 4+ card scenes must use at least 3 distinct layouts (cta excluded)
  - every data card (not cta) needs a "source"
  - manifest needs "sources" with at least 2 entries
Usage: python scripts/variety_check.py manifests/V003.json [qc/V003_variety.json]
"""
import json
import os
import sys


def check(mf):
    errs, warns = [], []
    cards = [s for s in mf.get("scenes", []) if s.get("type") == "card"]
    lays = [c.get("layout", "stat") for c in cards]
    body = [x for x in lays if x != "cta"]
    for i in range(len(lays) - 2):
        if lays[i] == lays[i + 1] == lays[i + 2]:
            errs.append(f"layout '{lays[i]}' used 3 times in a row (cards {i + 1}-{i + 3})")
    if len(lays) >= 4:
        top = max(set(body), key=body.count) if body else None
        if top and body.count(top) / len(body) > 0.5:
            errs.append(f"layout '{top}' is {body.count(top)}/{len(body)} of cards (max 50%)")
        if len(set(body)) < 3:
            errs.append(f"only {len(set(body))} distinct layouts across {len(lays)} cards (need 3+)")
    for i, c in enumerate(cards):
        if c.get("layout") != "cta" and not c.get("source"):
            errs.append(f"card {i + 1} ({c.get('layout')}) has no source")
    if len(mf.get("sources", [])) < 2:
        errs.append("manifest 'sources' needs at least 2 entries")
    if not cards:
        warns.append("no card scenes")
    return {"layouts": lays, "errors": errs, "warnings": warns, "pass": not errs}


if __name__ == "__main__":
    mf = json.load(open(sys.argv[1]))
    r = check(mf)
    if len(sys.argv) > 2:
        os.makedirs(os.path.dirname(sys.argv[2]) or ".", exist_ok=True)
        json.dump(r, open(sys.argv[2], "w"), indent=1)
    print(json.dumps(r, indent=1))
    sys.exit(0 if r["pass"] else 1)
