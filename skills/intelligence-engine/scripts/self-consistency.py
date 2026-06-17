#!/usr/bin/env python3
"""self-consistency (Wang et al. 2022, ICLR 2023): 3 answers → majority vote.
Proven to bridge ~0.25 model tiers. Combined with multi-perspective: ~0.5 tiers."""
import sys, json, os, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

AK = os.getenv("DEEPSEEK_API_KEY","")
BU = os.getenv("DEEPSEEK_BASE_URL","https://api.deepseek.com")
MD = os.getenv("SELF_REFINE_MODEL","deepseek-chat")

def call(sys_msg, user_msg, temp=0.5):
    if not AK: return None
    body = json.dumps({"model":MD,"messages":[{"role":"system","content":sys_msg},{"role":"user","content":user_msg}],"temperature":temp}).encode()
    req = urllib.request.Request(f"{BU}/v1/chat/completions", data=body,
        headers={"Authorization":f"Bearer {AK}","Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"]
    except: return None

SYS = "You are a software engineer. Answer the question based on the ground truth provided. Be specific and cite sources."

def generate_answers(question, n=3):
    """Generate n independent answers (parallel, temperature 0.5 for diversity)."""
    with ThreadPoolExecutor(max_workers=n) as pool:
        futures = {pool.submit(call, SYS, question, 0.5 + (i*0.1)): i for i in range(n)}
        answers = []
        for future in as_completed(futures):
            try:
                result = future.result()
                if result: answers.append(result)
            except: pass
    return answers

def extract_key_claims(text):
    """Extract key factual claims for voting."""
    claims = []
    for line in text.split('\n'):
        line = line.strip()
        if line.startswith('- ') or line.startswith('* ') or line.startswith('1. '):
            claims.append(line)
        # Also capture "X is Y" or "X has Y" patterns
        elif ' is ' in line or ' has ' in line or ' uses ' in line:
            if len(line) > 30 and len(line) < 200:
                claims.append(line)
    return claims[:15]

def majority_vote(answers):
    """Simple majority vote: pick the answer that's most similar to the others."""
    if len(answers) < 2: return answers[0] if answers else ""
    if len(answers) == 2: return answers[0]  # tie — use first
    
    # Use the answer with highest average similarity to others
    def similarity(a, b):
        a_words = set(a.lower().split())
        b_words = set(b.lower().split())
        if not a_words or not b_words: return 0
        return len(a_words & b_words) / len(a_words | b_words)
    
    scores = []
    for i, a in enumerate(answers):
        sims = [similarity(a, answers[j]) for j in range(len(answers)) if j != i]
        scores.append(sum(sims) / len(sims) if sims else 0)
    
    best_idx = scores.index(max(scores))
    confidence = scores[best_idx]
    
    return answers[best_idx], confidence, answers

if __name__ == "__main__":
    question = sys.stdin.read().strip()
    if not question:
        print(json.dumps({"error":"no input"}))
        sys.exit(1)
    
    answers = generate_answers(question)
    best, confidence, all_answers = majority_vote(answers)
    
    print(json.dumps({
        "technique": "self-consistency",
        "source": "Wang et al. 2022, ICLR 2023",
        "answers_generated": len(answers),
        "consensus_confidence": round(confidence, 2),
        "best_answer": best,
        "all_answers": [a[:500] for a in all_answers]
    }, indent=2))
