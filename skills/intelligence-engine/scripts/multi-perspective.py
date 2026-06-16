#!/usr/bin/env python3
"""multi-perspective debate (Du et al. 2023) — 4 real API calls, 3 perspectives, 1 judge.
Call 1: Conservative/correctness-first expert
Call 2: Pragmatic/efficiency-first expert
Call 3: Creative/edge-case-first expert
Call 4: Judge synthesizes best answer from all three
Zero deps. stdlib only. Parallel calls for speed."""
import sys, json, os, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    except Exception as e: return f"ERROR: {e}"

SYS_A = """You are a CONSERVATIVE software engineer. Your priority is correctness, safety, and reliability above all else. You never use experimental features or unproven patterns. You prefer battle-tested solutions with strong community support. When uncertain, you choose the safer option and flag risks explicitly. You cite specific documentation, version numbers, and compatibility concerns."""

SYS_B = """You are a PRAGMATIC software engineer. Your priority is developer velocity, simplicity, and maintainability. You choose the approach that gets the job done fastest with the least complexity. You prefer solutions that are easy to understand, test, and deploy. You optimize for the team's time, not theoretical perfection. You're opinionated about reducing complexity."""

SYS_C = """You are a CREATIVE software engineer. Your priority is finding non-obvious solutions and edge cases others miss. You think laterally about the problem. You question assumptions in the question itself. You find clever shortcuts, novel architectures, and unexpected failure modes. You are the person who asks 'what if we didn't need that at all?'"""

SYS_JUDGE = """You are a TECHNICAL JUDGE synthesizing three expert opinions. Your job:
1. Identify where all three experts agree → high confidence
2. Identify where experts disagree → analyze why, pick the strongest argument
3. Produce a single cohesive answer that combines the best of all perspectives
4. Flag any remaining uncertainties explicitly
5. Be decisive. Don't average opinions — pick the best parts of each.

CRITICAL: Only cite facts you can verify. If you're uncertain about a specific claim, say so."""

def multi_perspective(question):
    """3 parallel calls, 1 judge call."""
    # Phase 1: 3 parallel perspective calls
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(call, SYS_A, question, 0.5): "conservative",
            pool.submit(call, SYS_B, question, 0.5): "pragmatic",
            pool.submit(call, SYS_C, question, 0.5): "creative",
        }
        perspectives = {}
        for future in as_completed(futures):
            role = futures[future]
            try:
                result = future.result()
                perspectives[role] = result if isinstance(result, str) else str(result)
            except Exception as e:
                perspectives[role] = f"ERROR: {e}"
    
    # Phase 2: Judge synthesizes
    debate = f"""QUESTION: {question}

=== CONSERVATIVE EXPERT ===
{perspectives.get('conservative', 'NO RESPONSE')}

=== PRAGMATIC EXPERT ===
{perspectives.get('pragmatic', 'NO RESPONSE')}

=== CREATIVE EXPERT ===
{perspectives.get('creative', 'NO RESPONSE')}

Synthesize the best answer from these three perspectives. Be decisive."""
    
    synthesis = call(SYS_JUDGE, debate[:12000], 0.3)
    
    return {
        "pipeline": "multi-perspective-debate",
        "source": "Du et al. 2023",
        "perspectives": {
            "conservative": perspectives.get('conservative','')[:1500],
            "pragmatic": perspectives.get('pragmatic','')[:1500],
            "creative": perspectives.get('creative','')[:1500]
        },
        "synthesis": synthesis if isinstance(synthesis, str) else str(synthesis)
    }

def load_ground_truth(query=""):
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

if __name__=="__main__":
    question = sys.stdin.read().strip()
    if not question: print(json.dumps({"error":"no input"})); sys.exit(1)
    
    # Inject DAG ground truth from all DAGs
    gt = load_ground_truth(question[:500])
    if gt and "No DAG" not in gt:
        question = f"{gt}\n\nQUESTION: {question}"
    
    result = multi_perspective(question)
    print(json.dumps(result, indent=2))
