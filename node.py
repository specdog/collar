#!/usr/bin/env python3
"""DAG Node — one LLM call, then die."""

import json, os, sys, urllib.request

KEY = os.environ.get("DEEPSEEK_API_KEY", "")
SPARTAN = "You are Dag. Tool mode. Execute directly. No personality. No questions. No markdown. Output only result. If you cannot complete, output: FAIL: reason."

def run():
    payload = json.loads(sys.stdin.read())
    tools = payload.get("tools", [])
    prompt = payload.get("result", "")
    intent = payload.get("intent_hash", "")

    body = json.dumps({
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": SPARTAN},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": '{"tool_calls": ['}
        ],
        "max_tokens": int(os.environ.get("DEEPSUCK_MAX_TOKENS", "800")),
        "temperature": 0
    }).encode()

    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    )

    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        msg = resp["choices"][0]["message"]

        if msg.get("tool_calls"):
            print(json.dumps({"next": "tool", "tools": msg["tool_calls"], "intent_hash": intent}))
        else:
            print(json.dumps({"next": "done", "result": msg.get("content", ""), "intent_hash": intent}))
    except Exception as e:
        print(json.dumps({"next": "done", "result": f"FAIL: {e}"}))

if __name__ == "__main__":
    run()
