#!/usr/bin/env python3
"""SSRF 回调监听器（仅绑定 127.0.0.1，用于证明 Halo 服务端确实发起了请求）。"""
import http.server
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "evidence", "callback.log")
CANARY = "HALO-SSRF-CANARY-7f3a91"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9999


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "lab-listener/1.0"

    def log_message(self, fmt, *args):
        pass

    def _record(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("utf-8", "replace") if n else ""
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "method": self.command,
            "path": self.path,
            "client": self.client_address[0],
            "headers": dict(self.headers),
            "body": body,
        }
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def _respond(self, with_body=True):
        rec = self._record()
        payload = (CANARY + "\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if with_body:
            self.wfile.write(payload)
        sys.stderr.write("[hit] %s %s from %s\n" % (rec["method"], rec["path"], rec["client"]))
        sys.stderr.flush()

    def do_HEAD(self):
        self._respond(with_body=False)

    def do_GET(self):
        self._respond()

    def do_POST(self):
        self._respond()


if __name__ == "__main__":
    http.server.HTTPServer.allow_reuse_address = True
    srv = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    sys.stderr.write("listener on http://127.0.0.1:%d\n" % PORT)
    sys.stderr.flush()
    srv.serve_forever()
