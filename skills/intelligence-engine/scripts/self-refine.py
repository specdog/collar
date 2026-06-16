#!/usr/bin/env python3
"""self-refine (Madaan 2023): critique→refine. +20%. Zero deps. DAG-grounded."""
import sys, json, os, urllib.request, urllib.error

AK = os.getenv("DEEPSEEK_API_KEY","")
BU = os.getenv("DEEPSEEK_BASE_URL","https://api.deepseek.com")
MD = os.getenv("SELF_REFINE_MODEL","deepseek-chat")

def call(sys_msg, user_msg, temp=0.3):
    if not AK: return {"error":"no key"}
    body = json.dumps({"model":MD,"messages":[{"role":"system","content":sys_msg},{"role":"user","content":user_msg}],"temperature":temp}).encode()
    req = urllib.request.Request(f"{BU}/v1/chat/completions", data=body,
        headers={"Authorization":f"Bearer {AK}","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except Exception as e: return {"error":str(e)}

CRIT = """You are a harsh reviewer. Find EVERY error, vague claim, or unsupported assertion.
Be specific about: wrong facts, missing sources, undefined metrics, hallucinated details, missing DAG grounding.
List each error on its own line starting with -"""

FIX = """You are fixing output based on critique. CRITICAL RULES:
1. Only cite entities/numbers that appear in the GROUND TRUTH below
2. If something is NOT in the ground truth, say "unverified" or "unknown" — NEVER invent
3. Never add specific numbers, dates, or counts unless they are in the ground truth
4. If the original claim can't be verified from ground truth, flag it as unverified

GROUND TRUTH (only these entities and facts exist):{ground_truth}"""

def critique(text):
    return call(CRIT, f"OUTPUT TO CRITIQUE:\n{text[:8000]}\n\nList all errors:")

def refine(orig, crit, ground_truth=""):
    prompt = f"ORIGINAL:\n{orig[:6000]}\n\nCRITIQUE:\n{crit[:6000]}\n\nFixed version (only cite from ground truth):"
    sys_msg = FIX.format(ground_truth=ground_truth if ground_truth else "\n[No ground truth available — flag all specific claims as unverified]")
    return call(sys_msg, prompt)

def load_ground_truth(query=""):
    """Load all DAG entities as ground truth string using dag-router."""
    try:
        import subprocess
        dr = os.path.join(os.path.dirname(__file__), "dag-router.py")
        cmd = ["python3", dr]
        if query: cmd.extend(["--query", query])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except: pass
    return "[No DAG ground truth available]"

def run(text, dag_path=None, cwd=None):
    # Load DAG ground truth from all DAGs using dag-router
    gt = load_ground_truth(text[:500])
    
    c = critique(text)
    if isinstance(c,dict): return {"error":str(c),"stage":"critique"}
    
    r = refine(text, c, gt)
    if isinstance(r,dict): return {"error":str(r),"stage":"refine","critique":c[:500]}
    
    return {
        "pipeline":"self-refine",
        "source":"Madaan et al. 2023 +20%",
        "dag_grounded": bool(gt),
        "dag_entities": gt[:500] if gt else "",
        "critique":c[:2000],
        "refined":r
    }

if __name__=="__main__":
    txt = sys.stdin.read().strip()
    if not txt: print(json.dumps({"error":"no input"})); sys.exit(1)
    print(json.dumps(run(txt), indent=2))
