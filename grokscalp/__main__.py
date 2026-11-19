from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from . import __version__, config
from .data import available_symbols, load_snapshot
from .engine import SignalEngine
from .render.card import render_card, render_short
from .vision import ChartReader

BANNER = r"""
  ____ ____   ___  _  __  ____   ____   _    _     ____
 / ___|  _ \ / _ \| |/ / / ___| / ___| / \  | |   |  _ \
| |  _| |_) | | | | ' /  \___ \| |    / _ \ | |   | |_) |
| |_| |  _ <| |_| | . \   ___) | |___/ ___ \| |___|  __/
 \____|_| \_\\___/|_|\_\ |____/ \____/_/   \_\_____|_|
   scalp engine · 11 evidence families · one card
"""


def _engine(args) -> SignalEngine:
    cal = None
    if not args.no_calibration:
        from .engine import load_calibration
        cal = load_calibration()
    return SignalEngine(equity=args.equity, risk_pct=args.risk, calibration=cal)


def cmd_signal(args) -> int:
    if args.fixture:
        from .data.fixture import load as load_fixture
        snap = load_fixture(args.fixture)
        args.symbol, args.tf = snap.symbol, snap.tf
    else:
        snap = load_snapshot(args.symbol, args.tf, live=args.live, bars=args.bars, seed=args.seed)
    chart = ChartReader().read(args.image, args.symbol, args.tf) if args.image else None
    card = _engine(args).analyse(snap, chart)
    if args.json:
        payload = asdict(card)
        payload.pop("snapshot", None)
        payload["generated_at"] = card.generated_at
        print(json.dumps(payload, indent=2, default=str, ensure_ascii=False))
        return 0
    if not args.quiet:
        print(BANNER)
    print(render_card(card, lang=args.lang))
    return 0


def cmd_scan(args) -> int:
    symbols = args.scan if isinstance(args.scan, list) and args.scan else available_symbols()[:12]
    tfs = [args.tf] if args.tf else ["5m"]
    engine = _engine(args)
    print(f"scanning {len(symbols)} symbols × {len(tfs)} timeframes "
          f"({'live' if args.live else 'synthetic'})\n")
    for sym in symbols:
        try:
            snap = load_snapshot(sym, tfs[0], live=args.live, bars=args.bars, seed=args.seed)
            card = engine.analyse(snap)
            print(render_short(card, lang=args.lang))
        except Exception as exc:
            print(f"{sym:<10} error: {exc}")
    return 0


def cmd_backtest(args) -> int:
    from .backtest import calibrate, format_report, run, write_calibration
    snap = load_snapshot(args.symbol, args.tf, live=args.live, bars=max(args.bars, 900), seed=args.seed)
    engine = _engine(args)
    print(f"walk-forward on {snap.symbol} {snap.tf} · {len(snap.series())} bars · source {snap.source}")
    res = run(snap, engine, horizon=args.horizon, max_steps=args.max_steps, min_prob=args.min_prob)
    print(format_report(res))
    if args.calibrate and res.get("by_regime"):
        cal = calibrate(res["by_regime"])
        path = write_calibration(cal)
        print(f"\ncalibration written to {path}: {cal}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="grokscalp", description="Crypto scalping signal engine.")
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--tf", default="5m", choices=list(config.TF_MINUTES))
    p.add_argument("--live", action="store_true", help="use public Binance data instead of the simulator")
    p.add_argument("--lang", default="fa", choices=["fa", "en"])
    p.add_argument("--image", help="chart screenshot to analyse")
    p.add_argument("--fixture", help="analyse a captured snapshot (see grokscalp/data/fixture.py)")
    p.add_argument("--json", action="store_true", help="machine-readable card")
    p.add_argument("--scan", nargs="*", help="scan a list of symbols (default: majors)")
    p.add_argument("--backtest", action="store_true", help="walk-forward validate instead of printing a card")
    p.add_argument("--calibrate", action="store_true", help="write config/calibration.json from the backtest")
    p.add_argument("--no-calibration", action="store_true", help="ignore config/calibration.json")
    p.add_argument("--bars", type=int, default=config.DEFAULT_BARS)
    p.add_argument("--horizon", type=int, default=24, help="backtest holding window in bars")
    p.add_argument("--max-steps", type=int, default=450)
    p.add_argument("--min-prob", type=float, default=0.55)
    p.add_argument("--equity", type=float, default=config.DEFAULT_EQUITY)
    p.add_argument("--risk", type=float, default=config.DEFAULT_RISK_PCT)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--version", action="version", version=f"grokscalp {__version__}")
    args = p.parse_args(argv)

    if args.backtest:
        return cmd_backtest(args)
    if args.scan is not None:
        return cmd_scan(args)
    return cmd_signal(args)


if __name__ == "__main__":
    sys.exit(main())
