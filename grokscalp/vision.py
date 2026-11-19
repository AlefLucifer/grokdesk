"""Chart screenshot analysis.

Two paths, in this order:

1. `vision-api` — an OpenAI-compatible vision model reads the screenshot and
   returns strict JSON (trend, levels, patterns, indicators it can see).
2. `vision-lite` — offline, no keys: Pillow finds the candle colours, rebuilds
   the high/low envelope column by column, and derives trend, range position
   and where price keeps getting rejected. It cannot read price labels, so it
   deliberately does not invent absolute levels.

If Pillow is not installed either, the reader returns `available=False` and the
engine simply runs without the vision family.
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.request
from pathlib import Path

from .indicators import clamp, linreg_slope
from .types import ChartReading

SYSTEM = """You are a senior crypto scalper reading a chart screenshot.
Return ONLY compact JSON with this schema:
{"timeframe_seen": str, "trend": -1|0|1, "trend_label": str,
 "range_position": 0..1, "support": [numbers], "resistance": [numbers],
 "patterns": [str], "indicators_seen": [str], "notes": [str], "confidence": 0..1}
Read the price axis and only report levels you can actually see. No prose."""


def _strip_json(txt: str) -> dict:
    txt = txt.strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt, flags=re.MULTILINE).strip()
    try:
        return json.loads(txt)
    except ValueError:
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except ValueError:
                pass
    return {}


class ChartReader:
    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 model: str | None = None, timeout: float = 45.0,
                 offline: bool = False) -> None:
        self.offline = offline
        self.key = None if offline else (
            api_key or os.getenv("VISION_API_KEY") or os.getenv("OPENAI_API_KEY")
            or os.getenv("XAI_API_KEY"))
        self.base = (base_url or os.getenv("VISION_BASE") or "https://api.openai.com/v1").rstrip("/")
        self.model = model or os.getenv("VISION_MODEL") or "gpt-4o-mini"
        self.timeout = timeout

    # -- public -----------------------------------------------------------
    def read(self, image: bytes | str | Path | None, symbol: str = "", tf: str = "") -> ChartReading:
        if not image:
            return ChartReading(available=False, method="none",
                                notes=["no screenshot supplied"])
        try:
            raw = Path(image).read_bytes() if isinstance(image, (str, Path)) else bytes(image)
        except OSError as exc:
            return ChartReading(available=False, method="none", notes=[f"image unreadable: {exc}"])
        if self.key:
            try:
                return self._read_api(raw, symbol, tf)
            except Exception as exc:  # fall back, never fail the card
                lite = self._read_lite(raw)
                lite.notes.append(f"vision api failed ({type(exc).__name__}); used offline reader")
                return lite
        return self._read_lite(raw)

    # -- api --------------------------------------------------------------
    def _read_api(self, raw: bytes, symbol: str, tf: str) -> ChartReading:
        mime = "image/png" if raw[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
        b64 = base64.b64encode(raw).decode()
        body = json.dumps({
            "model": self.model,
            "temperature": 0,
            "max_tokens": 700,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": [
                    {"type": "text", "text": f"Asset {symbol or 'unknown'}, I trade it on {tf or 'unknown'}. "
                                             "Read the screenshot and return the JSON."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ]},
            ],
        }).encode()
        req = urllib.request.Request(self.base + "/chat/completions", data=body,
                                     headers={"Authorization": f"Bearer {self.key}",
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            out = json.loads(r.read())
        data = _strip_json(out["choices"][0]["message"]["content"])
        if not data:
            raise ValueError("model did not return JSON")
        sup = [float(x) for x in data.get("support", []) if isinstance(x, (int, float))]
        res = [float(x) for x in data.get("resistance", []) if isinstance(x, (int, float))]
        return ChartReading(
            available=True, method="vision-api",
            trend=int(clamp(float(data.get("trend", 0)), -1, 1)),
            trend_label=str(data.get("trend_label", "unknown")),
            range_position=clamp(float(data.get("range_position", 0.5))),
            support=sorted(sup)[:4], resistance=sorted(res)[:4],
            patterns=[str(x) for x in data.get("patterns", [])][:5],
            indicators_seen=[str(x) for x in data.get("indicators_seen", [])][:8],
            timeframe_seen=str(data.get("timeframe_seen", "")),
            notes=[str(x) for x in data.get("notes", [])][:6],
            confidence=clamp(float(data.get("confidence", 0.6))),
            raw=data,
        )

    # -- offline ----------------------------------------------------------
    def _read_lite(self, raw: bytes) -> ChartReading:
        try:
            from PIL import Image
        except ImportError:
            return ChartReading(available=False, method="none",
                                notes=["Pillow not installed: install `pillow` for the offline chart reader"])
        try:
            from io import BytesIO
            img = Image.open(BytesIO(raw)).convert("RGB")
        except Exception as exc:
            return ChartReading(available=False, method="none", notes=[f"cannot decode image: {exc}"])

        w, h = img.size
        if w > 900:
            img = img.resize((900, int(h * 900 / w)))
            w, h = img.size
        px = img.load()
        bull_cols: dict[int, list[int]] = {}
        bear_cols: dict[int, list[int]] = {}
        for x in range(w):
            for y in range(h):
                r, g, b = px[x, y]
                if g > 85 and (g - r) > 35 and g > b * 0.8:      # green / teal candles
                    bull_cols.setdefault(x, []).append(y)
                elif r > 85 and (r - g) > 35 and r > b * 0.65:   # red / maroon candles
                    bear_cols.setdefault(x, []).append(y)

        xs = sorted(set(bull_cols) | set(bear_cols))
        if len(xs) < 30:
            return ChartReading(available=False, method="vision-lite",
                                notes=["no candle colours found — is this a light-theme chart of a "
                                       "different palette? try the vision API path"])
        # longest contiguous run of candle columns = the plot area
        runs: list[list[int]] = [[xs[0]]]
        for x in xs[1:]:
            if x - runs[-1][-1] <= 3:
                runs[-1].append(x)
            else:
                runs.append([x])
        plot = max(runs, key=len)
        lo_x, hi_x = plot[0], plot[-1]
        step = max(1, len(plot) // 160)
        cols = plot[::step]

        highs, lows, mids = [], [], []
        for x in cols:
            ys = bull_cols.get(x, []) + bear_cols.get(x, [])
            if not ys:
                continue
            highs.append(min(ys))
            lows.append(max(ys))
        if len(highs) < 10:
            return ChartReading(available=False, method="vision-lite", notes=["candles too sparse to read"])
        top, bottom = min(highs), max(lows)
        span = max(bottom - top, 1)
        norm = [1.0 - (m - top) / span for m in mids or [(a + b) / 2 for a, b in zip(highs, lows)]]

        slope = linreg_slope(norm[-40:]) if len(norm) >= 40 else linreg_slope(norm)
        trend = 1 if slope > 0.0015 else -1 if slope < -0.0015 else 0
        last = norm[-1]
        rng = max(norm) - min(norm)
        pos = clamp((last - min(norm)) / rng) if rng > 0 else 0.5

        # rejection rows: places where many candles stop at the same height
        row_hits: dict[int, int] = {}
        for x in cols:
            for y in (bull_cols.get(x, []) + bear_cols.get(x, [])):
                if y in (top, bottom):
                    continue
                row_hits[y // 3] = row_hits.get(y // 3, 0) + 1
        hot = sorted(row_hits.items(), key=lambda kv: -kv[1])[:4]
        rejections = [round(1.0 - (row * 3 - top) / span, 3) for row, _ in hot]

        last_third = norm[-max(8, len(norm) // 3):]
        first_third = norm[:max(8, len(norm) // 3)]
        patterns = []
        if max(last_third) > max(first_third) and min(last_third) > min(first_third):
            patterns.append("higher highs and higher lows visible on the screenshot")
        if max(last_third) < max(first_third) and min(last_third) < min(first_third):
            patterns.append("lower highs and lower lows visible on the screenshot")
        if (max(last_third) - min(last_third)) < (max(first_third) - min(first_third)) * 0.55:
            patterns.append("range compression into the right edge")
        if last > 0.92:
            patterns.append("price pressed against the top of the visible range")
        if last < 0.08:
            patterns.append("price pressed against the bottom of the visible range")

        return ChartReading(
            available=True, method="vision-lite", trend=trend,
            trend_label="up" if trend > 0 else "down" if trend < 0 else "sideways",
            range_position=round(pos, 3), patterns=patterns,
            timeframe_seen="", support=[], resistance=[],
            notes=[
                f"offline reader: {len(cols)} candle columns across x {lo_x}–{hi_x}",
                f"normalised envelope {min(norm):.2f}–{max(norm):.2f}, slope {slope:+.4f}/column",
                "rejection clusters at normalised heights " + ", ".join(f"{r:.2f}" for r in rejections),
                "price axis cannot be read offline, so no absolute levels are claimed",
            ],
            confidence=0.38,
            raw={"columns": len(cols), "rejections": rejections},
        )
