from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from dashboard import server
from dashboard.server import analyze_logs


def test_dashboard_aggregates_success_and_failure_without_exposing_log_content(tmp_path) -> None:
    now = datetime(2026, 9, 30, 5, 0, tzinfo=timezone.utc)
    records = [
        {"ts": (now - timedelta(hours=2)).isoformat(), "event": "request_received"},
        {"ts": (now - timedelta(minutes=2)).isoformat(), "event": "request_received", "payload": {"message_preview": "private text"}},
        {"ts": (now - timedelta(minutes=2)).isoformat(), "event": "response_sent", "latency_ms": 100, "ttft_ms": 30, "tool_success": True, "cost_usd": 0.002, "tokens_in": 20, "tokens_out": 50, "quality_score": 0.8},
        {"ts": (now - timedelta(minutes=1)).isoformat(), "event": "request_received"},
        {"ts": (now - timedelta(minutes=1)).isoformat(), "event": "request_failed", "tool_success": False, "error_type": "RuntimeError"},
    ]
    path = tmp_path / "logs.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in records), encoding="utf-8")

    dashboard = analyze_logs(now=now, log_path=path)

    assert dashboard["summary"]["requests"] == 2
    assert dashboard["summary"]["errors"] == 1
    assert dashboard["summary"]["error_rate_pct"] == 50
    assert dashboard["summary"]["retrieval_success_pct"] == 50
    assert dashboard["summary"]["p95"] == 100
    assert dashboard["summary"]["cost_usd"] == 0.002
    assert dashboard["summary"]["tokens_out"] == 50
    assert dashboard["summary"]["quality"] == 0.8
    assert len(dashboard["series"]) == 2
    assert "private text" not in json.dumps(dashboard)


def test_incident_log_view_uses_real_matching_records_and_escapes_html(monkeypatch, tmp_path) -> None:
    path = tmp_path / "logs.jsonl"
    path.write_text(
        json.dumps({"correlation_id": "req-1a2b3c4d", "event": "response_sent", "payload": "<script>alert(1)</script>"})
        + "\n"
        + json.dumps({"correlation_id": "req-ffffffff", "event": "request_received"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "LOG_PATH", path)

    page = server.incident_log_page("req-1a2b3c4d").decode("utf-8")

    assert "response_sent" in page
    assert "req-ffffffff" not in page
    assert "<script>" not in page
    assert "&lt;script&gt;" in page
