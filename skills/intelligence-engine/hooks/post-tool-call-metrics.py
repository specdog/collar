#!/usr/bin/env python3
"""post_tool_call hook — DSPy metrics tracker."""
import sys, json
from pathlib import Path

M = Path.home() / ".deepsuck" / "metrics"; M.mkdir(parents=True, exist_ok=True)
CATS = {"read_file":"knowledge","search_files":"knowledge","browser_navigate":"research","terminal":"exec","write_file":"code","patch":"code"}

if __name__ == "__main__":
    try: p = json.loads(sys.stdin.read())
    except: p = {}
    sid = p.get("session_id","default"); tn = p.get("tool_name","?"); ti = p.get("tool_input",{})
    fp = M / f"{sid}.json"
    d = json.loads(fp.read_text()) if fp.exists() else {}
    d["total"] = d.get("total",0)+1
    d[f"cat_{CATS.get(tn,'other')}"] = d.get(f"cat_{CATS.get(tn,'other')}",0)+1
    if tn == "read_file" and ".dag" in str(ti.get("path","")): d["dag_loads"] = d.get("dag_loads",0)+1
    fp.write_text(json.dumps(d, indent=2))
    print(json.dumps({}))
