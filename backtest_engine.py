"""Historical, long-only research backtest from archived prices and timestamped decisions.

This is a hypothetical model, not brokerage execution. Signals are applied only after
their observation timestamp; daily close-to-close returns start on the next bar.
"""
from __future__ import annotations
from datetime import datetime, timezone
from math import sqrt
from statistics import mean, median
from typing import Any

def _time(value):
    if not value: return None
    try: d=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    except (TypeError,ValueError): return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)

def _close(bar):
    try: v=float(bar.get("close",bar.get("c")))
    except (TypeError,ValueError): return None
    return v if v>0 else None

def run_backtest(price_bars: dict[str,list[dict]], snapshots: list[dict],
                 initial_capital: float=10000, fee_bps: float=5,
                 benchmark_bars: list[dict]|None=None) -> dict[str,Any]:
    """Equal-weight CANDIDATE universe, cash otherwise; snapshots only affect later bars."""
    if initial_capital<=0 or fee_bps<0: raise ValueError("Capital must be positive and fees non-negative")
    series={}
    for symbol,bars in price_bars.items():
        rows=[]
        for b in bars:
            t=_time(b.get("bar_at",b.get("t"))); c=_close(b)
            if t and c: rows.append((t,c))
        rows.sort()
        if rows: series[symbol.upper()]=rows
    if not series: return {"status":"NO_PRICE_DATA","equity_curve":[],"metrics":{},"trades":[]}
    snap=[]
    for s in snapshots:
        t=_time(s.get("observed_at") or s.get("generated_at"))
        dec=s.get("investment_review") or {}
        decision=str(dec.get("decision") or s.get("decision") or "WATCH").upper()
        symbol=str(s.get("symbol","")).upper()
        if t and symbol in series: snap.append((t,symbol,decision))
    snap.sort()
    dates=sorted({t for rows in series.values() for t,c in rows})
    close_at={sym:{t:c for t,c in rows} for sym,rows in series.items()}
    # Use only dates with prices for at least one symbol; mark each symbol at last known close.
    active={}; cursor=0; cash=float(initial_capital); units={}; equity=initial_capital
    curve=[]; trades=[]; prev_values={}
    daily_returns=[]
    for day in dates:
        while cursor<len(snap) and snap[cursor][0]<day:
            _,sym,decision=snap[cursor]; active[sym]=decision; cursor+=1
        prices={sym:max((t for t in mp if t<=day),default=None) for sym,mp in close_at.items()}
        prices={sym:close_at[sym][t] for sym,t in prices.items() if t is not None}
        # portfolio target: equal weights across symbols whose latest available signal is CANDIDATE
        selected=sorted(sym for sym,d in active.items() if d=="CANDIDATE" and sym in prices)
        value=sum(units.get(sym,0)*prices[sym] for sym in prices)+cash
        target={sym:(value/len(selected))/prices[sym] for sym in selected} if selected else {}
        # Rebalance on signal changes/daily price availability; charge turnover costs.
        turnover=sum(abs(target.get(sym,0)-units.get(sym,0))*prices[sym] for sym in prices)
        cost=turnover*fee_bps/10000
        cash=value-sum(target.get(sym,0)*prices[sym] for sym in prices)-cost
        units=target
        equity=cash+sum(units.get(sym,0)*p for sym,p in prices.items())
        ret=equity/curve[-1]["equity"]-1 if curve else 0
        if curve: daily_returns.append(ret)
        curve.append({"date":day.isoformat(),"equity":round(equity,2),"return_pct":round(ret*100,5)})
        if turnover>0: trades.append({"date":day.isoformat(),"turnover":round(turnover,2),"cost":round(cost,2),"positions":selected})
    # Benchmark buy-and-hold, normalized at its first bar in the test window.
    bench=[]
    for b in benchmark_bars or []:
        t=_time(b.get("bar_at",b.get("t"))); c=_close(b)
        if t and c: bench.append((t,c))
    bench.sort(); b0=bench[0][1] if bench else None
    benchmark_return=(bench[-1][1]/b0-1)*100 if b0 else None
    vals=[x["equity"] for x in curve]
    peak=initial_capital; maxdd=0
    for v in vals:
        peak=max(peak,v); maxdd=min(maxdd,(v/peak-1)*100)
    n=len(daily_returns); avg=mean(daily_returns) if n else 0
    vol=(sqrt(sum((x-avg)**2 for x in daily_returns)/(n-1))*sqrt(252)*100) if n>1 else None
    sharpe=(avg/(sqrt(sum((x-avg)**2 for x in daily_returns)/(n-1)))*sqrt(252)) if n>1 and sum((x-avg)**2 for x in daily_returns)>0 else None
    total=(equity/initial_capital-1)*100
    years=max((dates[-1]-dates[0]).total_seconds()/(365.25*86400),0) if len(dates)>1 else 0
    annual=((equity/initial_capital)**(1/years)-1)*100 if years>0 and equity>0 else None
    return {"status":"OK","method":"timestamped_candidate_equal_weight_cash_v1","initial_capital":initial_capital,
      "equity_curve":curve,"trades":trades,"metrics":{"total_return_pct":round(total,3),
      "annualized_return_pct":round(annual,3) if annual is not None else None,
      "benchmark_return_pct":round(benchmark_return,3) if benchmark_return is not None else None,
      "max_drawdown_pct":round(maxdd,3),"annualized_volatility_pct":round(vol,3) if vol is not None else None,
      "sharpe_ratio":round(sharpe,3) if sharpe is not None else None,"bars":len(curve),"rebalance_events":len(trades)},
      "assumptions":["CANDIDATE=long; WATCH/AVOID/unknown=cash","Equal weight across active candidates",
      "Signal usable strictly after observed_at","Close-to-close daily bars","Fee applied to turnover; no taxes or slippage beyond fee"],
      "warning":"Hypothetical backtest on archived data; incomplete coverage, survivorship/selection bias and sparse snapshots can distort results. Not investment advice."}
