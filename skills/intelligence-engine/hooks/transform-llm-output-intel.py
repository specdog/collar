#!/usr/bin/env python3
"""transform_llm_output hook — ENFORCEMENT, not warning.
Runs pipeline audit. If refined output exists, REPLACES the original.
The model's raw output never reaches the user without verification.
This is a wall. Not a suggestion."""
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
    
    # DEBUG: log actual payload structure
    import os as _os
    debug_file = _os.path.expanduser("~/.deepsuck/metrics/hook_debug.json")
    try:
        with open(debug_file, "w") as f:
            json.dump({"keys": list(payload.keys()), "has_extra": "extra" in payload, "extra_keys": list(payload.get("extra", {}).keys()) if isinstance(payload.get("extra"), dict) else str(type(payload.get("extra")))}, f)
    except: pass

    text = payload.get("extra", {}).get("text", "")
    # Also try top-level text field
    if not text:
        text = payload.get("text", "")
    
    # Skip trivial responses
    if not text or len(text) < 80:
        print(json.dumps({}))
        sys.exit(0)
    
    # Skip if already pipeline-audited (prevent infinite loop)
    if "[PIPELINE" in text:
        print(json.dumps({}))
        sys.exit(0)
    
    use_fast = len(text) < 1000
    
    refined = run_pipeline(text, fast=use_fast)
    
    if refined:
        # ENFORCEMENT: replace original with refined output
        # The user never sees the unverified original
        tag = "fast" if use_fast else "full"
        print(json.dumps({"text": f"[VERIFIED — {tag} pipeline]\n\n{refined}"}))
    else:
        # Pipeline failed — let original through but flag it
        print(json.dumps({"text": f"[UNVERIFIED — pipeline audit failed]\n\n{text}"}))
