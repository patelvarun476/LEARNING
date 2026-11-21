#!/usr/bin/env python3
"""Journal gate: win rate, payoff ratio and data-quality check for the
ORACLE-ENGINE v4 Trade Journal (Airtable base app0D7AYsXqrfMLIV, table Trades).

Input: a JSON snapshot of the Trades table, a list of records shaped like
  {"id": "rec...", "ticker": "MU", "entry_date": null, "entry": 38.12,
   "shares": 55, "exit_date": "2026-11-16", "exit": 33.99, "pnl": -226.9,
   "exit_rule": "Zombie Cleanup", "setup": "Semi / AI", "notes": "..."}
Claude refreshes the snapshot through the Airtable connector before each run.

Usage:
  python3 oracle/journal_gate.py oracle/journal_snapshot.json
  python3 oracle/journal_gate.py SNAPSHOT --min-trades 20

Gate (defaults, change with flags):
  PASS only when there are at least --min-trades closed trades with every
  required field filled, no unresolved placeholders, and positive expectancy
  (average $ per closed trade > 0). Anything else is BLOCKED, with the reasons.

Note: the table has no Stop field, so a true R multiple cannot be computed.
"Avg R:R" here is the payoff ratio: average winning $ / average losing $.
"""
import argparse
import json
import sys
from collections import defaultdict

REQUIRED = ["ticker", "entry_date", "entry", "shares", "exit_date", "exit", "pnl", "exit_rule", "setup"]
PLACEHOLDER_WORDS = ("UPDATE with actual", "back-calculated", "Fill entry/exit", "CONFIRM if", "Confirm entry")


def base_ticker(t):
    return t.split(" (")[0].strip().upper()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot")
    ap.add_argument("--min-trades", type=int, default=20)
    a = ap.parse_args()

    recs = json.load(open(a.snapshot))
    closed = [r for r in recs if r.get("exit_date")]
    open_ = [r for r in recs if not r.get("exit_date")]

    complete, flagged = [], []
    for r in closed:
        missing = [f for f in REQUIRED if r.get(f) in (None, "")]
        placeholder = any(w.lower() in (r.get("notes") or "").lower() for w in PLACEHOLDER_WORDS)
        if missing or placeholder:
            flagged.append((r, missing, placeholder))
        if r.get("pnl") is not None:
            complete.append(r)

    # Duplicates: same ticker closed more than once on the same exit date.
    dup = defaultdict(list)
    for r in closed:
        dup[(base_ticker(r["ticker"]), r["exit_date"])].append(r["id"])
    dups = {k: v for k, v in dup.items() if len(v) > 1}

    wins = [r["pnl"] for r in complete if r["pnl"] > 0]
    losses = [-r["pnl"] for r in complete if r["pnl"] <= 0]
    n = len(complete)
    win_rate = 100.0 * len(wins) / n if n else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    payoff = avg_win / avg_loss if avg_loss else 0.0
    expectancy = (sum(wins) - sum(losses)) / n if n else 0.0

    reasons = []
    fully_clean = n - sum(1 for r, m, p in flagged if r.get("pnl") is not None)
    if fully_clean < a.min_trades:
        reasons.append("%d clean closed trades, need %d" % (fully_clean, a.min_trades))
    if expectancy <= 0:
        reasons.append("expectancy %+.2f per trade (must be > 0)" % expectancy)
    if dups:
        reasons.append("%d duplicate closed trades" % sum(len(v) - 1 for v in dups.values()))
    if flagged:
        reasons.append("%d closed trades missing fields or still placeholders" % len(flagged))
    gate = "PASS" if not reasons else "BLOCKED"

    print("Win Rate: %.1f%% | Avg R:R: %.2f:1 | Gate: %s" % (win_rate, payoff, gate))
    print()
    print("Records: %d total, %d closed (%d with a $ result), %d open" % (len(recs), len(closed), n, len(open_)))
    print("Closed with a $ result: %d wins, %d losses. Avg win $%.2f, avg loss $%.2f, net $%.2f, expectancy $%.2f/trade"
          % (len(wins), len(losses), avg_win, avg_loss, sum(wins) - sum(losses), expectancy))
    print("Currencies are mixed (CAD and USD rows); $ totals are a rough sum, not converted.")
    if reasons:
        print("\nBLOCKED because:")
        for x in reasons:
            print("  - " + x)
    if dups:
        print("\nDuplicates (same ticker, same exit date):")
        for (t, d), ids in sorted(dups.items()):
            print("  %-8s %s  %s" % (t, d, ", ".join(ids)))
    if flagged:
        print("\nClosed trades to fix:")
        for r, missing, placeholder in sorted(flagged, key=lambda x: x[0]["ticker"]):
            why = []
            if missing:
                why.append("missing " + ", ".join(missing))
            if placeholder:
                why.append("prices are estimates, not real fills")
            print("  %-18s %s  %s" % (r["ticker"], r["id"], "; ".join(why)))
    return 0 if gate == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
