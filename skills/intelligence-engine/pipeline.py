#!/usr/bin/env python3
"""
UNIFIED INTELLIGENCE PIPELINE
Ground truth -> Multi-perspective -> Self-refine -> Verified output.
One file. All pieces. Production.

Usage:
  echo "question" | python3 pipeline.py
  echo "question" | python3 pipeline.py --fast  (skip multi-perspective)
"""
import sys, json, os, subprocess, urllib.request, urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── CONFIG ──────────────────────────────────────────────────────────
AK = os.getenv("DEEPSEEK_API_KEY","")
BU = os.getenv("DEEPSEEK_BASE_URL","https://api.deepseek.com")
MD = os.getenv("SELF_REFINE_MODEL","deepseek-chat")
HOME = Path.home()
SCRIPTS = HOME / ".deepsuck" / "skills" / "intelligence-engine" / "scripts"
ENV_FILE = HOME / ".deepsuck" / ".env"

# ── API ─────────────────────────────────────────────────────────────
def load_key():
    global AK
    if AK: return
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().split('\n'):
            if line.startswith('DEEPSEEK_API_KEY='):
                AK = line.split('=',1)[1].strip().strip('"').strip("'")
                return

def call(sys_msg, user_msg, temp=0.3):
    if not AK: load_key()
    if not AK: return "ERROR: no API key"
    body = json.dumps({"model":MD,"messages":[{"role":"system","content":sys_msg},{"role":"user","content":user_msg}],"temperature":temp}).encode()
    req = urllib.request.Request(f"{BU}/v1/chat/completions", data=body,
        headers={"Authorization":f"Bearer {AK}","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except Exception as e: return f"ERROR: {e}"

# ── GROUND TRUTH ────────────────────────────────────────────────────
def load_ground_truth(question):
    """Load DAG entities + codebase matches + fact store for the question."""
    parts = []
    
    # DAGs
    try:
        dr = str(SCRIPTS / "dag-router.py")
        r = subprocess.run(["python3", dr, "--query", question[:200]],
            capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            parts.append(r.stdout.strip()[:3000])  # keep first 3000 chars of DAG output
    except: pass
    
    # Codebase
    try:
        cs = str(SCRIPTS / "codebase-search.py")
        r = subprocess.run(["python3", cs, "--json"],
            input=question, capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            data = json.loads(r.stdout)
            if data.get("files"):
                lines = [f"\nCODEBASE ({data['files']} files):"]
                for f in data["results"][:5]:
                    lines.append(f"  {f['path']}")
                    for l in f['snippet'].split('\n')[:20]:
                        lines.append(f"  {l}")
                parts.append("\n".join(lines))
    except: pass
    
    # Facts
    try:
        fs = str(SCRIPTS / "fact-store.py")
        r = subprocess.run(["python3", fs, "--recall"],
            input=question, capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            facts = json.loads(r.stdout).get("facts",[])
            if facts:
                flines = [f"\nVERIFIED FACTS ({len(facts)}):"]
                for f in facts[:6]:
                    flines.append(f"  [{f.get('topic','?')}] {f.get('text','')[:200]}")
                parts.append("\n".join(flines))
    except: pass
    
    return "\n".join(parts) if parts else "[No ground truth available]"

# ── MULTI-PERSPECTIVE ───────────────────────────────────────────────
SYS_A = "You are a CONSERVATIVE engineer. Correctness and safety above all. Never use experimental features. Flag every risk. Cite specific docs, versions, constraints."
SYS_B = "You are a PRAGMATIC engineer. Velocity and simplicity above all. Choose the approach that ships fastest with least complexity. Be opinionated. Cut scope."
SYS_C = "You are a CREATIVE engineer. Find non-obvious solutions and edge cases others miss. Question assumptions. Find clever shortcuts. Ask 'what if we didn't need that at all?'"
SYS_JUDGE = "You are a TECHNICAL JUDGE. Synthesize three expert opinions into one decisive answer. Pick the best parts of each. Flag remaining uncertainties. Be specific."

def multi_perspective(question):
    """3 parallel expert calls + 1 judge synthesis."""
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(call, SYS_A, question, 0.5): "conservative",
            pool.submit(call, SYS_B, question, 0.5): "pragmatic",
            pool.submit(call, SYS_C, question, 0.5): "creative",
        }
        perspectives = {}
        for future in as_completed(futures):
            role = futures[future]
            try: perspectives[role] = str(future.result())
            except: perspectives[role] = "ERROR"
    
    debate = f"QUESTION: {question}\n\n=== CONSERVATIVE ===\n{perspectives.get('conservative','NO RESPONSE')[:3000]}\n\n=== PRAGMATIC ===\n{perspectives.get('pragmatic','NO RESPONSE')[:3000]}\n\n=== CREATIVE ===\n{perspectives.get('creative','NO RESPONSE')[:3000]}\n\nSynthesize the best answer. Be decisive. Combine the strongest arguments."
    return call(SYS_JUDGE, debate[:12000], 0.3)

# ── SELF-REFINE ─────────────────────────────────────────────────────
CRITIQUE_SYS = "You are a ruthless reviewer. For the text, identify every single error — factual inaccuracies, missing edge cases, vague claims. For each error, state what is wrong and cite the specific evidence that contradicts it. Be decisive. Never hedge. Output each error as: - ERROR: [description] | EVIDENCE: [citation]"
REFINE_SYS = """You are fixing output based on critique. CRITICAL RULES:
1. Only cite facts/entities that appear in the GROUND TRUTH
2. If something is NOT in the ground truth, say "unverified" — NEVER invent
3. Never add specific numbers, dates, or counts unless they are in the ground truth
4. If the original claim can't be verified, flag it as unverified"""

def self_refine(text, ground_truth=""):
    """Critique -> DAG-grounded refine."""
    c = call(CRITIQUE_SYS, f"OUTPUT TO CRITIQUE:\n{text[:8000]}\n\nList all errors:")
    if c.startswith("ERROR"): return text  # fallback to original
    
    prompt = f"ORIGINAL:\n{text[:6000]}\n\nCRITIQUE:\n{c[:6000]}\n\nGROUND TRUTH:\n{ground_truth[:5000]}\n\nFixed version (only cite from ground truth):"
    r = call(REFINE_SYS, prompt)
    if r.startswith("ERROR"): return text
    
    return r

# ── MAIN PIPELINE ───────────────────────────────────────────────────
def run(question, fast=False):
    load_key()
    
    # Phase 1: Gather ground truth
    gt = load_ground_truth(question)
    
    # Phase 2: Build enriched question
    enriched = f"GROUND TRUTH:\n{gt[:5000]}\n\nQUESTION: {question}"
    
    # Phase 3: Generate (multi-perspective or single pass)
    if fast:
        answer = call("You are a software engineer. Answer based on ground truth.", enriched)
    else:
        answer = multi_perspective(enriched)
    
    if answer.startswith("ERROR"):
        return {"error": answer, "pipeline": "failed"}
    
    # Phase 4: Self-refine — use just the DAG portion (most relevant ground truth)
    dag_gt = gt.split('CODEBASE')[0].split('VERIFIED FACTS')[0] if gt else ""
    refined = self_refine(answer, dag_gt[:5000])
    
    return {
        "pipeline": "unified",
        "ground_truth_dags": len([l for l in gt.split('\n') if l.startswith('[')]),
        "ground_truth_chars": len(gt),
        "answer": refined
    }

# ── CLI ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    fast = "--fast" in sys.argv
    question = sys.stdin.read().strip()
    if not question:
        print(json.dumps({"error": "no input"}))
        sys.exit(1)
    
    result = run(question, fast)
    if "error" in result:
        print(json.dumps(result, indent=2))
    else:
        print(result["answer"])
