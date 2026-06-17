#!/usr/bin/env python3
"""pre_llm_call hook — ground truth injection (compact)."""
import sys, json, os, subprocess
from pathlib import Path

SCRIPTS = Path.home() / ".dag" / "skills" / "intelligence-engine" / "scripts"
DAG_ROUTER = str(SCRIPTS / "dag-router.py")
FACT_STORE = str(SCRIPTS / "fact-store.py")

def run(script, args, stdin="", timeout=5):
    try:
        r = subprocess.run(["python3", script] + args, input=stdin, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0: return r.stdout.strip()
    except: pass
    return ""

def load_truth(query):
    parts = []
    dag = run(DAG_ROUTER, ["--query", query[:200]], timeout=5)
    if dag: parts.append(dag[:4000])
    facts = run(FACT_STORE, ["--recall"], stdin=query, timeout=3)
    if facts:
        try:
            flist = json.loads(facts).get("facts",[])
            if flist:
                parts.append("FACTS: " + " | ".join(f["text"][:120] for f in flist[:4]))
        except: pass
    return "\n".join(parts) if parts else ""

if __name__ == "__main__":
    try: payload = json.loads(sys.stdin.read())
    except: payload = {}
    tool_input = payload.get("tool_input", {})
    query = json.dumps(tool_input) if tool_input else ""
    truth = load_truth(query)
    print(json.dumps({"context": truth if truth else ""}))
