#!/usr/bin/env python3
"""
knowledge-fetch.py — Live research puller
Searches GitHub/arXiv for latest relevant work before answering.

Usage: echo "topic" | python3 knowledge-fetch.py
"""
import sys, json, subprocess, urllib.request, urllib.parse

def search_github(topic: str, n: int = 5) -> list:
    """Search GitHub for relevant repos."""
    try:
        q = urllib.parse.quote(f"{topic} LLM reasoning technique")
        url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page={n}"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return [
                {"name": r["full_name"], "stars": r["stargazers_count"], 
                 "desc": (r.get("description") or "")[:200]}
                for r in data.get("items", [])[:n]
            ]
    except Exception as e:
        return [{"error": str(e)}]

if __name__ == "__main__":
    topic = sys.stdin.read().strip()
    if not topic:
        print(json.dumps({"error": "no topic"}))
        sys.exit(1)
    
    repos = search_github(topic)
    print(json.dumps({
        "technique": "knowledge_integration",
        "source": "live GitHub search",
        "topic": topic,
        "repos": repos,
        "instruction": "Incorporate relevant findings into your answer. Cite sources."
    }, indent=2))
