#!/usr/bin/env python3
"""Minimal GEPA (Genetic-Pareto Prompt Evolution). ~100 lines. No DSPy. No litellm.
Algorithm:
  1. Generate N prompt variants via LLM reflection on failures
  2. Test each variant on evaluation cases
  3. Pareto-select: keep variants that are better AND different
  4. Crossover: combine best variants
  5. Repeat for K generations
Based on: GEPA paper (ICLR 2026 Oral), gepars Rust implementation."""
import sys, json, os, urllib.request, random

AK = os.getenv("DEEPSEEK_API_KEY","")
BU = "https://api.deepseek.com"
MD = "deepseek-chat"

def load_key():
    global AK
    if AK: return
    env = os.path.expanduser("~/.deepsuck/.env")
    if os.path.exists(env):
        for line in open(env):
            if "DEEPSEEK_API_KEY" in line and "=" in line:
                AK = line.split("=",1)[1].strip().strip('"').strip("'")
                return

def call(sys_msg, user_msg, temp=0.3):
    body = json.dumps({"model":MD,"messages":[{"role":"system","content":sys_msg},{"role":"user","content":user_msg}],"temperature":temp}).encode()
    req = urllib.request.Request(f"{BU}/v1/chat/completions", data=body,
        headers={"Authorization":f"Bearer {AK}","Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"]

def mutate(prompt, failures, temp=0.8):
    """Reflective mutation: LLM sees what failed and proposes a fix."""
    sys_msg = "You are a prompt engineer. Given a prompt and its failures, rewrite it to fix the failures. Be specific. Output only the rewritten prompt."
    user_msg = f"CURRENT PROMPT:\n{prompt}\n\nFAILURES (what went wrong):\n{failures}\n\nRewrite to fix these failures:"
    try:
        return call(sys_msg, user_msg, temp).strip()
    except: return prompt

def crossover(parent_a, parent_b):
    """Combine two prompts: take structure from A, insights from B."""
    sys_msg = "Combine the best elements of two prompts into one superior prompt. Output only the combined prompt."
    user_msg = f"PROMPT A:\n{parent_a}\n\nPROMPT B:\n{parent_b}\n\nCombined prompt:"
    try:
        return call(sys_msg, user_msg, 0.5).strip()
    except: return parent_a

def evaluate(prompt, test_cases):
    """Score a prompt on test cases. Returns (accuracy, diversity)."""
    scores = []
    for question, expected, forbidden in test_cases:
        try:
            answer = call(prompt, question).lower()
            good = sum(1 for kw in expected if kw.lower() in answer)
            bad = sum(1 for kw in forbidden if kw.lower() in answer)
            scores.append(max(0, good - bad))
        except: scores.append(0)
    return sum(scores) / len(scores) if scores else 0

def pareto_select(population, scores, min_diversity=0.1):
    """Keep best AND diverse variants."""
    selected = []
    for i, (prompt, score) in enumerate(zip(population, scores)):
        # Check if different enough from already selected
        too_similar = False
        for s_prompt, _ in selected:
            similarity = len(set(prompt.split()) & set(s_prompt.split())) / max(len(set(prompt.split())), 1)
            if similarity > (1 - min_diversity):
                too_similar = True
                break
        if not too_similar or score > max(scores) * 0.9:
            selected.append((prompt, score))
    selected.sort(key=lambda x: x[1], reverse=True)
    return selected[:3]  # Keep top 3

def optimize(initial_prompt, test_cases, generations=3, population=4):
    """Run GEPA optimization."""
    prompts = [initial_prompt]
    best = (initial_prompt, evaluate(initial_prompt, test_cases))
    
    for gen in range(generations):
        print(f"\nGen {gen+1}: best_score={best[1]:.1f}")
        
        # Generate variants via reflective mutation
        new_prompts = []
        for prompt in prompts[-population:]:
            # Simulate failures for reflection
            failures = "Failed to detect false claims. Output was too vague. Missed specific entity names."
            mutated = mutate(prompt, failures)
            if len(mutated) > 20:
                new_prompts.append(mutated)
        
        # Crossover best pairs
        if len(prompts) >= 2:
            for i in range(len(prompts)-1):
                crossed = crossover(prompts[i], prompts[i+1])
                if len(crossed) > 20:
                    new_prompts.append(crossed)
        
        # Evaluate
        scored = [(p, evaluate(p, test_cases)) for p in new_prompts]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Pareto select
        selected = pareto_select([p for p,_ in scored], [s for _,s in scored])
        prompts = [p for p,_ in selected]
        
        if selected and selected[0][1] > best[1]:
            best = selected[0]
            print(f"  IMPROVED: {best[1]:.1f}")
    
    return best[0], best[1]

if __name__ == "__main__":
    load_key()
    
    original = "You are a harsh reviewer. Find EVERY error. Be specific about wrong facts, missing edge cases, vague language. List each error on its own line."
    
    test_cases = [
        ("The Technique entity has 42 sub-types.", 
         ["unverified", "not", "no", "false"], 
         ["correct", "accurate"]),
        ("HardBlock uses Redis for caching.", 
         ["no", "not", "unverified", "false"], 
         ["yes", "correct"]),
        ("The fact store has thousands of verified facts.", 
         ["unverified", "not", "cannot"], 
         ["confirmed", "verified"]),
    ]
    
    print("=== GEPA PROMPT OPTIMIZER ===")
    best_prompt, best_score = optimize(original, test_cases, generations=2, population=3)
    
    print(f"\n=== RESULT (score: {best_score:.1f}) ===")
    print(best_prompt)
