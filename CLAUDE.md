# LEARNING — trading workspace

Trader skills live in `.claude/skills/trader-*` (paper trading by default).
Oracle tools live in `oracle/`.

## Before every scan

1. Run `python3 oracle/data_feed.py` and show the block to the user, unedited.
   It prints VIX, TSM, AMD, QQQ, SPY, SOXL with the data time. If the oldest
   quote is stale, say so.
2. Run the journal gate (below). If it prints `Gate: BLOCKED`, say so and list
   the reasons before scanning.

## Journal gate

Airtable base `ORACLE-ENGINE v4 — Trade Journal` (`app0D7AYsXqrfMLIV`), table
`Trades` (`tblB84VthdPrVftVd`). Read it through the Airtable connector (no API
key is needed or stored), write every record to `oracle/journal_snapshot.json`
in the shape documented at the top of `oracle/journal_gate.py`, then run:

    python3 oracle/journal_gate.py oracle/journal_snapshot.json

Never edit or delete journal rows to make the gate pass.

## Auto-journal on trade confirm

When the user explicitly confirms they placed a trade (their own words, with
ticker, shares and price), create ONE row in `Trades` through the Airtable
connector:

| Field | ID | Value |
| --- | --- | --- |
| Ticker | fldWJAEISQab9tre8 | ticker as traded (e.g. `MU`, `MDA.TO`) |
| Entry Date | fld8fXDSiPdCmKCfG | fill date, YYYY-MM-DD (New York date) |
| Entry Price | fldOLQ1P76U5IPm0W | actual fill price |
| Shares | fldfVNZSeHT2jC7Gb | shares filled |
| Setup Type | fldb2eNVZrU4RCa2T | existing option: `Leveraged ETF`, `Semi / AI` or `Other` |
| Notes | fld6IcrG5FXNFC8yB | currency (CAD/USD), stop, target, the plan's reason, `OPEN POSITION` |

Leave Exit Date, Exit Price, % Gain/Loss, $ Gain/Loss and Exit Rule empty: the
user fills exit data. Never invent or back-calculate a price. If any entry value
is unknown, ask instead of writing the row. Show the created row to the user.
A scan hit, a plan or a PASS from trader-risk is NOT a confirmed trade.
