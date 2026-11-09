"""Alertmanager 本地告警接收器（观察期留痕）。

只监听 monitoring 网络内部，不向宿主机发布端口；把 webhook 通知追加为 JSONL，
供 14 天观察期核查与收口举证。仅保留排障所需的标签/状态字段，不记录请求头、
不记录任何凭据。文件由 compose bind mount 到 ./alert-sink/，已加入 .gitignore。

查看：docker compose -f monitoring/monitoring-deployment.yml exec alert-webhook-logger \
      sh -c 'tail -n 20 /data/alert-events.jsonl'
"""

import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OUT = os.environ.get("ALERT_SINK_FILE", "/data/alert-events.jsonl")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        body = b'{"status":"ok"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/alerts":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            payload = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            self.send_error(400)
            return
        if not isinstance(payload, dict):
            self.send_error(400)
            return

        alerts = payload.get("alerts") or []
        record = {
            "received_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "receiver": payload.get("receiver"),
            "status": payload.get("status"),
            "group_labels": payload.get("groupLabels"),
            "alert_count": len(alerts),
            "alerts": [
                {
                    "alertname": (a.get("labels") or {}).get("alertname"),
                    "job": (a.get("labels") or {}).get("job"),
                    "instance": (a.get("labels") or {}).get("instance"),
                    "severity": (a.get("labels") or {}).get("severity"),
                    "status": a.get("status"),
                    "starts_at": a.get("startsAt"),
                    "summary": (a.get("annotations") or {}).get("summary"),
                }
                for a in alerts
                if isinstance(a, dict)
            ],
        }
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt, *args):
        # 逐请求日志无价值，落盘文件即证据；异常由 send_error 产生 stderr。
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9094), Handler).serve_forever()
