#!/usr/bin/env python3
"""Deepsuck Gateway — routes payloads to nodes, kills old nodes, verifies signatures."""

import json, hmac, hashlib, os, subprocess, shutil, tempfile, signal
from http.server import HTTPServer, BaseHTTPRequestHandler

ROOM_KEY = os.environ.get("DEEPSUCK_ROOM_KEY") or os.urandom(32).hex()
WORK_DIR = os.path.join(tempfile.gettempdir(), "deepsuck-nodes")

class Gateway(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.error(400, "invalid json")
            return

        sig = payload.pop("signature", "")
        expected = hmac.new(ROOM_KEY.encode(), json.dumps(payload, sort_keys=True).encode(), hashlib.sha256).hexdigest()
        if sig != expected:
            self.error(403, "bad signature")
            return

        self.log_message("routing to: %s", payload.get("next", "llm"))

        # Spawn fresh node
        node_dir = tempfile.mkdtemp(dir=WORK_DIR, prefix="node-")
        try:
            result = subprocess.run(
                ["python3", f"{os.path.dirname(__file__)}/node.py"],
                input=json.dumps(payload),
                capture_output=True, text=True, timeout=30,
                cwd=node_dir,
                env={**os.environ, "DEEPSUCK_WORKDIR": node_dir}
            )
            self.log_message("node exited: %d", result.returncode)
            output = result.stdout.strip()
            if result.returncode != 0:
                output = output or result.stderr or "node error"
        except subprocess.TimeoutExpired:
            output = json.dumps({"next": "done", "result": "FAIL: node timed out"})
        finally:
            shutil.rmtree(node_dir, ignore_errors=True)

        # Parse and sign response
        try:
            resp = json.loads(output)
        except json.JSONDecodeError:
            resp = {"next": "done", "result": output}

        resp["signature"] = hmac.new(ROOM_KEY.encode(), json.dumps(resp, sort_keys=True).encode(), hashlib.sha256).hexdigest()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode())

    def error(self, code, msg):
        self.send_response(code); self.end_headers()
        self.wfile.write(json.dumps({"next": "done", "result": f"FAIL: {msg}"}).encode())
    
    def log_message(self, fmt, *args):
        pass  # silent

if __name__ == "__main__":
    os.makedirs(WORK_DIR, exist_ok=True)
    port = int(os.environ.get("DEEPSUCK_PORT", "9999"))
    print(f"Gateway: http://127.0.0.1:{port}  key={ROOM_KEY[:8]}...")
    HTTPServer(("127.0.0.1", port), Gateway).serve_forever()
