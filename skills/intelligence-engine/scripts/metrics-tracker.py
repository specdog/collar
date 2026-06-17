#!/usr/bin/env python3
"""
metrics-tracker.py — DSPy-style session optimizer (Khattab et al. 2024, Stanford)
Tracks per-session metrics. Outputs SOUL.md improvement suggestions.

Usage: python3 metrics-tracker.py --session-id <id> --action <log|report>
  log: record a metric event
  report: analyze all metrics, suggest SOUL.md improvements
"""
import sys, json, os, datetime
from pathlib import Path

METRICS_DIR = Path.home() / ".dag" / "metrics"
METRICS_DIR.mkdir(parents=True, exist_ok=True)

METRICS = {
    "self_caught_errors": 0,
    "accurate_markers": 0,
    "inflated_markers": 0,
    "trapdoor_failures": 0,
    "dag_reloads": 0,
    "tot_uses": 0,
    "reflexion_cycles": 0,
    "knowledge_fetches": 0,
    "user_corrections": 0,
    "total_turns": 0,
}

def log_metric(session_id: str, key: str, value: int = 1):
    path = METRICS_DIR / f"{session_id}.json"
    data = METRICS.copy()
    if path.exists():
        data.update(json.loads(path.read_text()))
    data[key] = data.get(key, 0) + value
    data["total_turns"] += 1
    path.write_text(json.dumps(data, indent=2))
    return data

def generate_report(session_id: str = None):
    """Analyze all sessions, generate SOUL.md improvement suggestions."""
    if session_id:
        paths = [METRICS_DIR / f"{session_id}.json"]
    else:
        paths = sorted(METRICS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)[:10]
    
    all_data = {}
    for p in paths:
        if p.exists():
            all_data[p.stem] = json.loads(p.read_text())
    
    suggestions = []
    total = sum(d.get("total_turns", 0) for d in all_data.values())
    total_corrections = sum(d.get("user_corrections", 0) for d in all_data.values())
    total_inflated = sum(d.get("inflated_markers", 0) for d in all_data.values())
    total_failures = sum(d.get("trapdoor_failures", 0) for d in all_data.values())
    
    if total_corrections > total * 0.1:
        suggestions.append("HIGH: User correction rate >10%. Strengthen negative space in SOUL.md.")
    if total_inflated > total * 0.05:
        suggestions.append("MEDIUM: Inflated [DAG: X/10] markers >5%. Strengthen External Confidence Verification section.")
    if total_failures > total * 0.15:
        suggestions.append("HIGH: Trapdoor failures >15%. Increase proactive DAG refresh frequency.")
    if total < 100:
        suggestions.append("LOW: Not enough data for reliable optimization. Continue collecting.")
    else:
        suggestions.append("INFO: Sufficient data. DSPy optimization can now propose specific SOUL.md wording changes.")
    
    return {
        "sessions_analyzed": len(all_data),
        "total_turns": total,
        "correction_rate": f"{total_corrections/max(total,1)*100:.1f}%",
        "marker_inflation_rate": f"{total_inflated/max(total,1)*100:.1f}%",
        "trapdoor_failure_rate": f"{total_failures/max(total,1)*100:.1f}%",
        "suggestions": suggestions,
        "dspy_note": "After 100+ turns, use these metrics to propose specific SOUL.md phrase optimizations per Khattab et al. 2024."
    }

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--session-id", default="default")
    p.add_argument("--action", choices=["log", "report"], default="report")
    p.add_argument("--key", default="total_turns")
    p.add_argument("--value", type=int, default=1)
    args = p.parse_args()
    
    if args.action == "log":
        result = log_metric(args.session_id, args.key, args.value)
    else:
        result = generate_report(args.session_id if args.session_id != "default" else None)
    
    print(json.dumps(result, indent=2))
