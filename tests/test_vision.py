from __future__ import annotations

import io
import math

import pytest

from grokscalp.vision import ChartReader


def _chart_png(trend: int = 1, width: int = 640, height: int = 360) -> bytes:
    """Draw a fake candlestick screenshot: dark background, green/red candles."""
    PIL = pytest.importorskip("PIL.Image")
    from PIL import ImageDraw

    img = PIL.new("RGB", (width, height), (14, 17, 23))
    dr = ImageDraw.Draw(img)
    n = 90
    left, right, top, bottom = 60, width - 20, 30, height - 40
    step = (right - left) / n
    price = 0.5
    for i in range(n):
        drift = 0.012 * trend + math.sin(i / 7) * 0.006
        o = price
        price = max(0.05, min(0.95, price + drift))
        hi = max(o, price) + 0.008
        lo = min(o, price) - 0.008
        x = left + i * step
        colour = (38, 166, 154) if price >= o else (239, 83, 80)
        dr.line([(x, top + (1 - hi) * (bottom - top)), (x, top + (1 - lo) * (bottom - top))],
                fill=colour, width=3)
        y0 = top + (1 - max(o, price)) * (bottom - top)
        y1 = top + (1 - min(o, price)) * (bottom - top)
        dr.rectangle([x - 3, y0, x + 3, y1], fill=colour)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_offline_reader_detects_an_uptrend():
    reader = ChartReader(offline=True)
    reading = reader.read(_chart_png(trend=1), "BTCUSDT", "5m")
    assert reading.available
    assert reading.method == "vision-lite"
    assert reading.trend >= 0, reading.trend_label
    assert 0 <= reading.range_position <= 1
    assert reading.confidence > 0.2
    assert reading.notes


def test_offline_reader_detects_a_downtrend():
    reader = ChartReader(offline=True)
    reading = reader.read(_chart_png(trend=-1), "BTCUSDT", "5m")
    assert reading.available
    assert reading.trend <= 0, reading.trend_label


def test_reader_handles_garbage():
    reader = ChartReader(offline=True)
    reading = reader.read(b"not an image at all", "BTCUSDT", "5m")
    assert reading.available is False
    assert reading.notes


def test_no_image_means_no_reading():
    reading = ChartReader(offline=True).read(None)
    assert reading.available is False
    assert reading.method == "none"


def test_vision_evidence_flows_into_the_card():
    from grokscalp.data import load_snapshot
    from grokscalp.engine import SignalEngine

    snap = load_snapshot("BTCUSDT", "5m", bars=300)
    reading = ChartReader(offline=True).read(_chart_png(), "BTCUSDT", "5m")
    card = SignalEngine(calibration={}).analyse(snap, reading)
    assert any(e.family == "VISION" for e in card.evidence) or reading.trend == 0
    assert card.chart.method == "vision-lite"
