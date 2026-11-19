from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

APP = Path(__file__).resolve().parents[1] / "grokscalp" / "ui" / "streamlit_app.py"


def test_dashboard_boots_without_exceptions():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.tabs, "expected the tabbed desk layout"
    assert any("GROK SCALP" in m.value for m in at.markdown)


def test_dashboard_renders_a_card_for_another_symbol():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=180)
    at.run()
    at.selectbox[0].select("ETHUSDT").run()
    assert not at.exception, [e.value for e in at.exception]
    text = " ".join(m.value for m in at.markdown)
    assert "ETHUSDT" in text
