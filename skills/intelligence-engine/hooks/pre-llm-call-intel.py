#!/usr/bin/env python3
"""pre_llm_call hook — unified ground truth injection.
DAG entities + codebase matches + fact store + walls."""
import sys, json, os, subprocess
from pathlib import Path

SCRIPTS = Path.home() / ".deepsuck" / "skills" / "intelligence-engine" / "scripts"
DAG_ROUTER = str(SCRIPTS / "dag-router.py")
CODE_SEARCH = str(SCRIPTS / "codebase-search.py")
FACT_STORE = str(SCRIPTS / "fact-store.py")

def run_script(script, args, stdin="", timeout=5):
    try:
        cmd = ["python3", script] + args
        r = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout)
        if r.returncode == 0: return r.stdout.strip()
    except: pass
    return ""

def load_ground_truth(query):
    parts = []
    
    # DAG entities
    dag = run_script(DAG_ROUTER, ["--query", query[:200]], timeout=5)
    if dag: parts.append(dag[:3000])
    
    # Codebase matches
    code = run_script(CODE_SEARCH, ["--json"], stdin=query, timeout=15)
    if code:
        try:
            data = json.loads(code)
            if data.get("files"):
                clines = [f"\nCODEBASE ({data['files']} files):"]
                for f in data["results"][:5]:
                    clines.append(f"  {f['path']}")
                    for l in f['snippet'].split('\n')[:15]:
                        clines.append(f"  {l}")
                parts.append("\n".join(clines)[:3000])
        except: pass
    
    # Facts
    facts = run_script(FACT_STORE, ["--recall"], stdin=query, timeout=3)
    if facts:
        try:
            flist = json.loads(facts).get("facts",[])
            if flist:
                flines = [f"\nVERIFIED FACTS ({len(flist)}):"]
                for f in flist[:6]:
                    flines.append(f"  [{f.get('topic','?')}] {f.get('text','')[:200]}")
                parts.append("\n".join(flines))
        except: pass
    
    return "\n".join(parts) if parts else ""

def build_injection(gt, facts_found):
    lines = ["=== GROUND TRUTH (injected by hook) ==="]
    if gt: lines.append(gt)
    lines.append("\nWALLS:")
    lines.append("  1. Only cite facts from the ground truth above")
    lines.append("  2. If not in ground truth -> say 'unverified'")
    lines.append("  3. Never hallucinate specifics. Never guess.")
    lines.append("  4. Read code files before editing. Query DAG before answering.")
    lines.append("=== END GROUND TRUTH ===")
    return "\n".join(lines)

if __name__ == "__main__":
    try: payload = json.loads(sys.stdin.read())
    except: payload = {}

    tool_input = payload.get("tool_input", {})
    query = json.dumps(tool_input) if tool_input else ""

    gt = load_ground_truth(query)
    injection = build_injection(gt, bool(gt))
    print(json.dumps({"context": injection}))
