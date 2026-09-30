"""Local read-only dashboard for the six panels in config/dashboard.yaml."""

from __future__ import annotations

import argparse
import html
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "logs.jsonl"
CONFIG_PATH = ROOT / "config" / "dashboard.yaml"
HTML_PATH = Path(__file__).with_name("index.html")


def percentile(values: list[float], p: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * p / 100) - 1)], 2)


def analyze_logs(now: datetime | None = None, log_path: Path = LOG_PATH) -> dict:
    now = now or datetime.now(timezone.utc)
    start = now - timedelta(minutes=60)
    rows: list[dict] = []
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                ts = datetime.fromisoformat(str(row["ts"]).replace("Z", "+00:00"))
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                continue
            if start <= ts <= now:
                row["_minute"] = ts.replace(second=0, microsecond=0).isoformat()
                rows.append(row)

    by_minute: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_minute[row["_minute"]].append(row)

    series = []
    for minute, events in sorted(by_minute.items()):
        received = [r for r in events if r.get("event") == "request_received"]
        sent = [r for r in events if r.get("event") == "response_sent"]
        failed = [r for r in events if r.get("event") == "request_failed"]
        tools = [r for r in events if isinstance(r.get("tool_success"), bool)]
        latencies = [float(r["latency_ms"]) for r in sent if isinstance(r.get("latency_ms"), (int, float))]
        ttfts = [float(r["ttft_ms"]) for r in sent if isinstance(r.get("ttft_ms"), (int, float))]
        qualities = [float(r["quality_score"]) for r in sent if isinstance(r.get("quality_score"), (int, float))]
        series.append({
            "minute": datetime.fromisoformat(minute).strftime("%H:%M"),
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "p99": percentile(latencies, 99),
            "ttft_p95": percentile(ttfts, 95),
            "traffic": len(received),
            "error_rate_pct": round(100 * len(failed) / len(received), 2) if received else 0,
            "retrieval_success_pct": round(100 * sum(r["tool_success"] for r in tools) / len(tools), 2) if tools else 0,
            "cost_usd": round(sum(float(r.get("cost_usd") or 0) for r in sent), 6),
            "tokens_in": sum(int(r.get("tokens_in") or 0) for r in sent),
            "tokens_out": sum(int(r.get("tokens_out") or 0) for r in sent),
            "quality": round(sum(qualities) / len(qualities), 3) if qualities else 0,
        })

    received_all = [r for r in rows if r.get("event") == "request_received"]
    sent_all = [r for r in rows if r.get("event") == "response_sent"]
    failed_all = [r for r in rows if r.get("event") == "request_failed"]
    tools_all = [r for r in rows if isinstance(r.get("tool_success"), bool)]
    latencies_all = [float(r["latency_ms"]) for r in sent_all if isinstance(r.get("latency_ms"), (int, float))]
    ttfts_all = [float(r["ttft_ms"]) for r in sent_all if isinstance(r.get("ttft_ms"), (int, float))]
    qualities_all = [float(r["quality_score"]) for r in sent_all if isinstance(r.get("quality_score"), (int, float))]
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]
    return {
        "as_of": now.isoformat(),
        "window_minutes": 60,
        "refresh_seconds": config["refresh_seconds"],
        "thresholds": {p["id"]: p["threshold"] for p in config["panels"]},
        "series": series,
        "summary": {
            "requests": len(received_all),
            "errors": len(failed_all),
            "p50": percentile(latencies_all, 50),
            "p95": percentile(latencies_all, 95),
            "p99": percentile(latencies_all, 99),
            "ttft_p95": percentile(ttfts_all, 95),
            "error_rate_pct": round(100 * len(failed_all) / len(received_all), 2) if received_all else 0,
            "retrieval_success_pct": round(100 * sum(r["tool_success"] for r in tools_all) / len(tools_all), 2) if tools_all else 0,
            "cost_usd": round(sum(float(r.get("cost_usd") or 0) for r in sent_all), 6),
            "tokens_in": sum(int(r.get("tokens_in") or 0) for r in sent_all),
            "tokens_out": sum(int(r.get("tokens_out") or 0) for r in sent_all),
            "quality": round(sum(qualities_all) / len(qualities_all), 3) if qualities_all else 0,
        },
    }


def incident_log_page(correlation_id: str) -> bytes:
    if not re.fullmatch(r"req-[0-9a-fA-F]{8}", correlation_id):
        raise ValueError("invalid correlation ID")
    matching = []
    if LOG_PATH.exists():
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("correlation_id") == correlation_id:
                matching.append(record)
    records = "\n".join(
        f"<section><h2>{html.escape(str(row.get('event', 'unknown')))}</h2>"
        f"<pre>{html.escape(json.dumps(row, ensure_ascii=False, indent=2))}</pre></section>"
        for row in matching
    ) or "<p>Không tìm thấy request này trong data/logs.jsonl.</p>"
    page = f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Incident log {correlation_id}</title><style>
    *{{box-sizing:border-box}}body{{margin:0;padding:clamp(18px,3vw,44px);background:#f2f5fa;color:#16243a;font:16px/1.5 system-ui,sans-serif}}header{{margin-bottom:20px}}p{{color:#53647c}}main{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}}section{{min-width:0;background:#fff;border:1px solid #d8e0ed;border-radius:16px;padding:18px}}h1{{margin:0;font-size:30px}}h2{{margin:0 0 12px;color:#254edb}}pre{{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.55 Consolas,monospace}}code{{color:#254edb}}@media(max-width:850px){{main{{grid-template-columns:1fr}}}}
    </style></head><body><header><p>DAY 13 · LOG GỐC TỪ <code>data/logs.jsonl</code></p><h1>Yêu cầu {html.escape(correlation_id)}</h1><p>Hai event được lọc trực tiếp từ file JSONL theo cùng correlation ID. Giờ log: UTC.</p></header><main>{records}</main></body></html>"""
    return page.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            content, mime = HTML_PATH.read_bytes(), "text/html; charset=utf-8"
        elif parsed.path == "/api/metrics":
            content = json.dumps(analyze_logs(), ensure_ascii=False).encode("utf-8")
            mime = "application/json; charset=utf-8"
        elif parsed.path == "/incident-log":
            try:
                content = incident_log_page(parse_qs(parsed.query).get("cid", [""])[0])
            except ValueError:
                self.send_error(400, "Invalid correlation ID")
                return
            mime = "text/html; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Dashboard: http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
