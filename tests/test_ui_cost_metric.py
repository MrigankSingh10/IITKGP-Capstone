"""The telemetry tab never shows an unknown price as $0."""
import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit", reason="UI dependencies are optional")
pytest.importorskip("pandas", reason="UI dependencies are optional")
pytest.importorskip("requests", reason="UI dependencies are optional")

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "app.py"


def trace(cost, prompt=900, completion=120, status="review_required"):
    return {"timestamp": "2026-11-26T10:00:00+00:00", "session_id": "s", "query": "q", "route_taken": "document_review",
            "latency_ms": 10.0, "prompt_tokens": prompt, "completion_tokens": completion,
            "estimated_cost_usd": cost, "citations": [], "status": status}


def cost_shown(tmp_path, monkeypatch, rows):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports/agent_traces.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    import requests

    def offline(*_args, **_kwargs):
        raise requests.ConnectionError("API not running in this test")
    monkeypatch.setattr("requests.get", offline)
    app = AppTest.from_file(str(APP))
    app.run()
    assert not app.exception
    metric = next(m for m in app.metric if m.label == "Est. Session Cost")
    return metric.value


@pytest.mark.parametrize("rows, expected", [
    ([trace(None), trace(None)], "Unavailable"),                          # no price configured
    ([trace(0.0)], "Unavailable"),                                        # older traces stored 0.0
    ([trace(0.002), trace(None)], "$0.002 (incomplete)"),                 # only some requests priced
    ([trace(0.002), trace(0.001)], "$0.003"),
    ([trace(None, prompt=0, completion=0, status="refused")], "$0"),       # no model call, nothing to pay
])
def test_cost_is_unavailable_or_incomplete_rather_than_zero(tmp_path, monkeypatch, rows, expected):
    assert cost_shown(tmp_path, monkeypatch, rows) == expected
