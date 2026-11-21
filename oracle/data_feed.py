#!/usr/bin/env python3
"""Oracle data feed: a fresh market snapshot to paste at the start of every scan.

Free Yahoo Finance chart data (unofficial, can lag; no API key).
Usage:
  python3 oracle/data_feed.py
  python3 oracle/data_feed.py --tickers TSM,AMD,NVDA --leveraged SOXL
"""
import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

UA = "Mozilla/5.0 (compatible; oracle-data-feed/1.0)"
NY = ZoneInfo("America/New_York")


def chart(sym, rng, interval):
    for host in ("query2", "query1"):
        url = "https://%s.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=%s" % (host, sym, rng, interval)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                res = json.load(r)["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            rows = [(t, c, v) for t, c, v in zip(res["timestamp"], q["close"], q["volume"]) if c is not None]
            return res["meta"], rows
        except Exception as e:  # try the other host
            err = e
    raise RuntimeError("%s: %s" % (sym, err))


def ny_time(ts):
    return datetime.fromtimestamp(ts, timezone.utc).astimezone(NY).strftime("%H:%M ET %a %b %d")


def m(v):
    return "%.1fm" % (v / 1e6)


def stock_line(sym, with_ma=True):
    meta, rows = chart(sym, "3mo", "1d")
    price = meta.get("regularMarketPrice") or rows[-1][1]
    vol = meta.get("regularMarketVolume") or rows[-1][2] or 0
    past = rows[-21:-1]  # the 20 sessions before the latest
    avg_vol = sum(r[2] or 0 for r in past) / len(past)
    closes = [r[1] for r in rows[-20:]]
    ma20 = sum(closes) / len(closes)
    line = "%s: $%.2f | vol: %s (20d avg: %s)" % (sym, price, m(vol), m(avg_vol))
    if with_ma:
        line += " | %% from 20dMA: %+.1f%%" % (100 * (price / ma20 - 1))
    return line, meta.get("regularMarketTime")


def index_line(sym):
    meta, rows = chart(sym, "1y", "1wk")
    price = meta.get("regularMarketPrice") or rows[-1][1]
    closes = [r[1] for r in rows[-20:]]
    ma = sum(closes) / len(closes)
    side = "ABOVE" if price > ma else "BELOW"
    return "%s: $%.2f | 20-week MA $%.2f: %s (%+.1f%%)" % (sym, price, ma, side, 100 * (price / ma - 1)), meta.get("regularMarketTime")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default="TSM,AMD")
    ap.add_argument("--indexes", default="QQQ,SPY")
    ap.add_argument("--leveraged", default="SOXL")
    a = ap.parse_args()

    now = datetime.now(NY)
    print("ORACLE DATA FEED | pulled %s | source: Yahoo Finance (free, can lag)" % now.strftime("%Y-%m-%d %H:%M ET %a"))
    times, errors = [], []

    def run(fn, *args):
        try:
            line, ts = fn(*args)
            print(line)
            if ts:
                times.append(ts)
        except Exception as e:
            errors.append(str(e))
            print("%s: DATA UNAVAILABLE" % args[0])

    try:
        meta, _ = chart("^VIX", "5d", "1d")
        print("VIX: %.2f | source: Yahoo | time: %s" % (meta["regularMarketPrice"], ny_time(meta["regularMarketTime"])))
        times.append(meta["regularMarketTime"])
    except Exception as e:
        errors.append(str(e))
        print("VIX: DATA UNAVAILABLE")
    for s in filter(None, a.tickers.split(",")):
        run(stock_line, s.strip().upper())
    for s in filter(None, a.indexes.split(",")):
        run(index_line, s.strip().upper())
    for s in filter(None, a.leveraged.split(",")):
        run(stock_line, s.strip().upper(), False)

    if times:
        oldest = min(times)
        age_h = (now.timestamp() - oldest) / 3600
        print("Data as of: %s (oldest quote %.1f h old)%s" % (
            ny_time(oldest), age_h, "  [market closed: last session's prices]" if age_h > 0.5 else ""))
    if errors:
        print("Errors: " + "; ".join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
