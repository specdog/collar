#!/usr/bin/env python3
"""transform_llm_output hook — full pipeline audit.
<1000 chars: skip. 200-1000 chars: --fast mode. >1000 chars: full multi-perspective."""
import sys, json, subprocess, os
from pathlib import Path

PIPELINE = str(Path.home() / ".deepsuck" / "skills" / "intelligence-engine" / "pipeline.py")
ENV_FILE = Path.home() / ".deepsuck" / ".env"

def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().split('\n'):
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def run_pipeline(text, fast=False):
    env = os.environ.copy()
    env.update(load_env())
    cmd = ["python3", PIPELINE]
    if fast: cmd.append("--fast")
    try:
        r = subprocess.run(cmd, input=text, capture_output=True, text=True, timeout=180, env=env)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except: pass
    return None

if __name__ == "__main__":
    try: payload = json.loads(sys.stdin.read())
    except: payload = {}

    text = payload.get("extra", {}).get("text", "")
    if not text or len(text) < 200:
        print(json.dumps({}))
        sys.exit(0)

    # Short responses: fast mode. Long responses: full multi-perspective.
    use_fast = len(text) < 1000
    mode = "fast" if use_fast else "full"
    
    refined = run_pipeline(text, fast=use_fast)
    if refined:
        print(json.dumps({"text": f"[PIPELINE AUDIT - {mode}]\n\n{refined}"}))
    else:
        print(json.dumps({}))
