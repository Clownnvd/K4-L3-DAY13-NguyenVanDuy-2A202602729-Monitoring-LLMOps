from __future__ import annotations

import json
import asyncio
import re
from pathlib import Path

import httpx

from app import logging_config
from app.main import app


def test_chat_response_log_exposes_quality_for_dashboard(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/chat",
                json={
                    "user_id": "student-01",
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "Explain observability",
                },
            )

    response = asyncio.run(send_request())

    assert response.status_code == 200
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    response_event = next(event for event in events if event["event"] == "response_sent")
    assert response_event["quality_score"] == response.json()["quality_score"]
    assert response_event["ttft_ms"] == response.json()["ttft_ms"]
    assert response_event["tool_name"] == "retrieval"
    assert response_event["tool_success"] is True


def test_request_id_is_returned_and_sensitive_context_is_scrubbed(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send(header: str) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/chat",
                headers={"x-request-id": header},
                json={
                    "user_id": "student-01",
                    "session_id": "student@vinuni.edu.vn",
                    "feature": "qa",
                    "message": "Contact 0901234567, CCCD 001099012345, card 4111 1111 1111 1111",
                },
            )

    response = asyncio.run(send("req-1a2b3c4d"))
    generated = asyncio.run(send("invalid-header"))

    assert response.status_code == generated.status_code == 200
    assert response.headers["x-request-id"] == "req-1a2b3c4d"
    assert re.fullmatch(r"req-[0-9a-f]{8}", generated.headers["x-request-id"])
    assert response.headers["x-response-time-ms"]
    assert response.json()["correlation_id"] == response.headers["x-request-id"]

    raw = log_path.read_text(encoding="utf-8")
    for secret in ("student@vinuni.edu.vn", "0901234567", "001099012345", "4111 1111 1111 1111"):
        assert secret not in raw
    events = [json.loads(line) for line in raw.splitlines()]
    assert {event["correlation_id"] for event in events if event.get("service") == "api"} == {
        response.headers["x-request-id"], generated.headers["x-request-id"]
    }
    assert all("user_id_hash" in event for event in events if event.get("service") == "api")


def test_formatted_exception_is_scrubbed_before_jsonl_write(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    try:
        raise RuntimeError("Synthetic failure for student@vinuni.edu.vn")
    except RuntimeError:
        logging_config.get_logger().exception("request_failed", service="api")

    raw = log_path.read_text(encoding="utf-8")
    assert "student@vinuni.edu.vn" not in raw
    assert "[REDACTED_EMAIL]" in raw
