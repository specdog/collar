#!/usr/bin/env python3
"""Lean prompt optimizer. No DSPy. No litellm. No bloat.
1. Take a prompt + test cases
2. Generate 3 variants via LLM
3. Test each on test cases
4. Pick best variant
5. Repeat N generations
~50 lines. Uses existing stdlib API call pattern."""
import sys, json, os, urllib.request, urllib.error

AK = os.getenv("DEEPSEEK_API_KEY","")
BU = "https://api.deepseek.com"
MD = "deepseek-chat"

def load_key():
    global AK
    if AK: return
    env_file = os.path.expanduser("~/.dag/.env")
    if os.path.exists(env_file):
        for line in open(env_file):
            if "DEEPSEEK_API_KEY" in line and "=" in line:
                AK = line.split("=",1)[1].strip().strip('"').strip("'")
                return

def call(sys_msg, user_msg, temp=0.3):
    body = json.dumps({"model":MD,"messages":[{"role":"system","content":sys_msg},{"role":"user","content":user_msg}],"temperature":temp}).encode()
    req = urllib.request.Request(f"{BU}/v1/chat/completions", data=body,
        headers={"Authorization":f"Bearer {AK}","Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]

OPTIMIZER_PROMPT = """You are a prompt engineer. Rewrite the following system prompt to be MORE EFFECTIVE.
Rules:
- Keep it concise. Every word must earn its place.
- Add specific instructions that prevent common failure modes
- Be direct. No politeness. No filler.
- Output ONLY the rewritten prompt. No explanation.

ORIGINAL PROMPT:
{original}

REWRITTEN PROMPT:"""

def generate_variants(original, n=3):
    """Generate N variants of the prompt."""
    variants = []
    for i in range(n):
        try:
            variant = call(OPTIMIZER_PROMPT, OPTIMIZER_PROMPT.format(original=original), temp=0.7 + (i*0.1))
            variant = variant.strip()
            if len(variant) > 20:
                variants.append(variant)
        except: pass
    return variants

def evaluate_prompt(prompt, test_cases):
    """Score a prompt on test cases. Returns average score (0-10)."""
    scores = []
    for question, expected_keywords in test_cases:
        try:
            answer = call(prompt, question).lower()
            score = sum(1 for kw in expected_keywords if kw.lower() in answer)
            scores.append(score)
        except:
            scores.append(0)
    return sum(scores) / len(scores) if scores else 0

def optimize(original_prompt, test_cases, generations=3, variants_per_gen=3):
    """Run evolution: generate variants, test, pick best, repeat."""
    best_prompt = original_prompt
    best_score = evaluate_prompt(original_prompt, test_cases)
    
    print(f"Gen 0: score={best_score:.1f}")
    
    for gen in range(generations):
        variants = generate_variants(best_prompt, variants_per_gen)
        for i, variant in enumerate(variants):
            score = evaluate_prompt(variant, test_cases)
            if score > best_score:
                best_score = score
                best_prompt = variant
                print(f"Gen {gen+1} variant {i+1}: score={score:.1f} IMPROVED")
            else:
                print(f"Gen {gen+1} variant {i+1}: score={score:.1f}")
    
    return best_prompt, best_score

if __name__ == "__main__":
    load_key()
    
    # Default test: optimize the critique prompt
    original = "You are a harsh reviewer. Find EVERY error. Be specific: wrong facts, missing edge cases, security issues, vague language, missing DAG grounding. List each error on its own line."
    
    test_cases = [
        ("The Technique entity has 17 sub-types and uses WebSocket for communication.", 
         ["unverified", "not in", "no", "false", "incorrect"]),
        ("HardBlock has states locked and unlocked, enforced by AuditTrapdoor.", 
         ["active", "violated", "toolgate", "not"]),
        ("The fact store has 2,347 verified facts.", 
         ["unverified", "no", "not in ground truth"]),
    ]
    
    if len(sys.argv) > 1:
        original = sys.argv[1]
    
    print("=== PROMPT OPTIMIZER ===")
    print(f"Original: {original[:100]}...")
    print()
    
    best, score = optimize(original, test_cases, generations=2, variants_per_gen=3)
    
    print(f"\nBEST (score {score:.1f}):")
    print(best)
