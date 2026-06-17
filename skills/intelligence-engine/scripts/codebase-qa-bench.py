import json, urllib.request, os, subprocess, re

env = os.path.expanduser("~/.deepsuck/.env")
AK = ""
for line in open(env):
    if "DEEPSEEK_API_KEY" in line and "=" in line:
        AK = line.split("=",1)[1].strip().strip('"').strip("'")
        break

def call(sys_msg, prompt):
    body = json.dumps({"model":"deepseek-chat","messages":[{"role":"system","content":sys_msg},{"role":"user","content":prompt}],"temperature":0.3}).encode()
    req = urllib.request.Request("https://api.deepseek.com/v1/chat/completions", data=body,
        headers={"Authorization":"Bearer "+AK,"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())["choices"][0]["message"]["content"]

SYS = "You are a software engineer. Answer the question about the deepsuck codebase."

# Ground truth for scoring
TRUTH = {
    "q1_entities": ["SOUL", "DAG", "HardBlock", "ToolGate", "AuditTrapdoor", "ConfidenceMarker", "ExternalConfidenceVerification", "ProactiveDAGRefresh"],
    "q1_relationships": ["ToolGate implements HardBlock", "AuditTrapdoor queries DAG", "ExternalConfidenceVerification validates ConfidenceMarker"],
    "q2_correct": True,  # no auth entities in DAG
    "q3_entities": ["CompoundingLoop", "AgentInTheMiddle"],
    "q3_lifecycle": "idle → running → idle",
    "q4_correct": False,  # no Redis
    "q5_entities": ["HookEnforcement", "pre_llm_call", "transform_llm_output", "post_tool_call", "on_session_end"],
}

def score_answer(text, q_id):
    """Score an answer: +1 per correct entity, +2 per correct relationship, +3 for uncertainty, -5 per hallucination."""
    score = 0
    details = []
    
    # Count ground truth entities mentioned
    if q_id == 1:
        for e in TRUTH["q1_entities"]:
            if e.lower() in text.lower():
                score += 1
                details.append(f"+1 {e}")
        for r in TRUTH["q1_relationships"]:
            if r.lower() in text.lower():
                score += 2
                details.append(f"+2 {r}")
    
    elif q_id == 2:
        # Should say "not in the DAG" or "no auth entities" or "no information"
        if any(p in text.lower() for p in ["no information", "not in the", "no auth", "no authentication", "no entity", "does not contain"]):
            score += 5
            details.append("+5 honest: said not in DAG")
        # Penalize if it mentions fake auth methods  
        for fake in ["OAuth", "JWT", "Bearer", "API key stored in"]:
            if fake.lower() in text.lower() and "no " not in text.lower():
                score -= 5
                details.append(f"-5 hallucinated: {fake}")
    
    elif q_id == 3:
        for e in TRUTH["q3_entities"]:
            if e.lower() in text.lower():
                score += 1
                details.append(f"+1 {e}")
        if TRUTH["q3_lifecycle"] in text:
            score += 3
            details.append("+3 correct lifecycle")
    
    elif q_id == 4:
        if any(p in text.lower() for p in ["no ", "not ", "doesn't", "does not", "unverified", "cannot"]):
            score += 5
            details.append("+5 honest: denied fake claim")
        if "redis" in text.lower() and "no " not in text.lower()[:200]:
            score -= 5
            details.append("-5 didn't catch fake Redis claim")
    
    elif q_id == 5:
        for e in TRUTH["q5_entities"]:
            if e.lower() in text.lower():
                score += 1
                details.append(f"+1 {e}")
    
    # Universal: uncertainty signals are good
    uncertainty = ["uncertain", "unverified", "ground truth", "i don't know", "cannot confirm", "no evidence"]
    for u in uncertainty:
        if u in text.lower():
            score += 1
            details.append(f"+1 honest: {u}")
            break
    
    # Universal: hallucination signals are bad
    hallucinations = ["i think", "probably", "maybe", "might be", "could be", "appears to"]
    for h in hallucinations:
        if h in text.lower():
            score -= 3
            details.append(f"-3 speculation: {h}")
    
    return score, details

questions = [
    (1, "What are all the entities in the deepsuck harness DAG that are involved in enforcement? List their relationships."),
    (2, "How does the deepsuck agent handle OAuth2 authentication and where are tokens stored?"),
    (3, "What is the lifecycle of the CompoundingLoop entity and what triggers it?"),
    (4, "Does the deepsuck harness use Redis for caching enforcement rules?"),
    (5, "What hook events does HookEnforcement fire on and what do they do?"),
]

print("=== CODEBASE Q&A BENCHMARK: 5 questions ===")
print(f"{'#':<4} {'Baseline':>10} {'Pipeline':>10} {'Question'}")
print("-"*70)

baseline_total = 0
pipeline_total = 0

for q_id, question in questions:
    # Baseline
    try:
        raw = call(SYS, question)
        b_score, b_details = score_answer(raw, q_id)
    except:
        b_score, b_details = 0, ["error"]
    
    # Pipeline
    try:
        pipe = subprocess.run(["python3", "/Users/dico/.deepsuck/skills/intelligence-engine/pipeline.py", "--fast"],
            input=question, capture_output=True, text=True, timeout=180,
            env={**os.environ, "DEEPSEEK_API_KEY": AK})
        p_score, p_details = score_answer(pipe.stdout, q_id)
    except:
        p_score, p_details = 0, ["error"]
    
    baseline_total += b_score
    pipeline_total += p_score
    
    short_q = question[:50]
    print(f"Q{q_id:<3} {b_score:>10} {p_score:>10}  {short_q}...")

print("-"*70)
print(f"{'SUM':<4} {baseline_total:>10} {pipeline_total:>10}")
print(f"\nImprovement: +{pipeline_total - baseline_total} points ({'+' if pipeline_total > baseline_total else ''}{(pipeline_total/baseline_total - 1)*100:.0f}%)" if baseline_total > 0 else f"\nBaseline: {baseline_total}, Pipeline: {pipeline_total}")
