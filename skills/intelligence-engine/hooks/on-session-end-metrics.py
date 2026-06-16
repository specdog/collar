#!/usr/bin/env python3
"""on_session_end hook — DSPy optimization report."""
import sys, json
from pathlib import Path
from datetime import datetime

M = Path.home() / ".deepsuck" / "metrics"
R = Path.home() / ".deepsuck" / "intel-reports"; R.mkdir(parents=True, exist_ok=True)

if __name__ == "__main__":
    try: p = json.loads(sys.stdin.read())
    except: p = {}
    sid = p.get("session_id","default")
    fp = M / f"{sid}.json"
    if not fp.exists(): print(json.dumps({"error":"no metrics"})); sys.exit(0)
    d = json.loads(fp.read_text())
    t = d.get("total",0)
    s = []
    if t == 0: s.append("NO DATA")
    else:
        k = d.get("cat_knowledge",0); r = d.get("cat_research",0); c = d.get("cat_code",0); dag = d.get("dag_loads",0)
        if k/t < 0.15: s.append(f"LOW KNOWLEDGE: {k}/{t}={k/t*100:.0f}% — strengthen DAG refresh")
        if r/t < 0.05 and t>20: s.append(f"LOW RESEARCH: {r}/{t}={r/t*100:.0f}% — strengthen grounding")
        if c>0 and dag==0: s.append("HARD BLOCK VIOLATION: code without DAG load")
        if t>50: s.append("DSPY READY: 50+ calls, run metrics-tracker for phrase optimization")
        if not s: s.append("OPTIMAL: all metrics healthy")
    rp = R / f"{sid}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    rp.write_text(json.dumps({"session":sid,"metrics":d,"suggestions":s},indent=2))
    print(json.dumps({"report":str(rp),"suggestions":len(s)}))
