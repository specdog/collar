#!/usr/bin/env python3
"""verify-answer.py -- Extract claims and output verification plan."""
import sys, json, re

def extract_claims(text):
    claims = []
    patterns = [
        (r'[A-Z][a-zA-Z]+(?:\s+[a-z]+){0,3}\s+(?:is|has|uses|supports|requires|provides)\s+[^.!?]+', 'statement'),
        (r'/[a-zA-Z0-9/._-]{5,}', 'path'),
        (r'v?\d+\.\d+\.\d+', 'version'),
        (r'https?://[^\s)]{10,}', 'url'),
    ]
    for pattern, claim_type in patterns:
        for match in re.finditer(pattern, text):
            t = match.group(0).strip()
            if t not in [c['text'] for c in claims]:
                claims.append({'text': t, 'type': claim_type})
    return claims

if __name__ == "__main__":
    dag = None
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == '--dag' and i+1 < len(args):
            dag = args[i+1]
    
    answer = sys.stdin.read().strip()
    if not answer:
        print(json.dumps({"error": "no input"}))
        sys.exit(1)
    
    claims = extract_claims(answer)
    for c in claims:
        c['verify'] = 'file_check' if c['type'] == 'path' else ('dag_check' if dag else 'manual')
    
    print(json.dumps({
        "pipeline": "verify-answer",
        "claims_found": len(claims),
        "claims": claims,
        "instruction": "Run verification for each claim. Re-generate answer with corrections."
    }, indent=2))
