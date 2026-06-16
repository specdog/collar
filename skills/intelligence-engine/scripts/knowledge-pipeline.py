#!/usr/bin/env python3
"""
knowledge-pipeline.py -- Live Research Pipeline
Fetches from ArXiv, SemanticScholar, GitHub APIs.
The internet is the training set. API-only, no local model needed.

Usage: echo "topic" | python3 knowledge-pipeline.py
       echo "topic" | python3 knowledge-pipeline.py --sources arxiv,github
"""
import sys, json, urllib.request, urllib.parse, urllib.error
from datetime import datetime
from xml.etree import ElementTree as ET

ARXIV_API = "http://export.arxiv.org/api/query"
SEMANTIC_API = "https://api.semanticscholar.org/graph/v1/paper/search"

def search_arxiv(topic, n=5):
    """Search ArXiv for recent papers."""
    try:
        params = urllib.parse.urlencode({
            "search_query": f"all:{topic}",
            "start": 0,
            "max_results": n,
            "sortBy": "relevance",
            "sortOrder": "descending"
        })
        url = f"{ARXIV_API}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "IntelligenceEngine/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            root = ET.fromstring(resp.read())
            papers = []
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns):
                papers.append({
                    "title": (entry.find("atom:title", ns).text or "").strip(),
                    "summary": ((entry.find("atom:summary", ns).text or "")[:300]).strip(),
                    "published": (entry.find("atom:published", ns).text or "")[:10],
                    "authors": [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns) if a.find("atom:name", ns) is not None][:5],
                    "url": entry.find("atom:id", ns).text or ""
                })
            return papers
    except Exception as e:
        return [{"error": f"ArXiv: {str(e)}"}]

def search_semantic_scholar(topic, n=5):
    """Search Semantic Scholar for papers."""
    try:
        params = urllib.parse.urlencode({
            "query": topic, "limit": n,
            "fields": "title,abstract,year,authors,url,citationCount"
        })
        url = f"{SEMANTIC_API}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "IntelligenceEngine/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            papers = []
            for p in data.get("data", []):
                papers.append({
                    "title": p.get("title", ""),
                    "abstract": (p.get("abstract") or "")[:300],
                    "year": p.get("year", ""),
                    "authors": [a.get("name", "") for a in p.get("authors", [])][:5],
                    "citations": p.get("citationCount", 0),
                    "url": p.get("url", "")
                })
            return papers
    except Exception as e:
        return [{"error": f"SemanticScholar: {str(e)}"}]

def search_github_repos(topic, n=5):
    """Search GitHub for relevant repositories."""
    try:
        q = urllib.parse.quote(f"{topic} LLM reasoning")
        url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page={n}"
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "IntelligenceEngine/1.0"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            repos = []
            for r in data.get("items", [])[:n]:
                repos.append({
                    "name": r["full_name"],
                    "stars": r["stargazers_count"],
                    "desc": (r.get("description") or "")[:200],
                    "url": r["html_url"],
                    "language": r.get("language", ""),
                    "updated": r.get("updated_at", "")[:10]
                })
            return repos
    except Exception as e:
        return [{"error": f"GitHub: {str(e)}"}]

def fetch_all(topic, sources=None):
    """Fetch from all or specified sources."""
    if sources is None:
        sources = ["arxiv", "semantic_scholar", "github"]

    results = {
        "topic": topic,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "sources": {}
    }

    if "arxiv" in sources:
        results["sources"]["arxiv"] = search_arxiv(topic)
    if "semantic_scholar" in sources:
        results["sources"]["semantic_scholar"] = search_semantic_scholar(topic)
    if "github" in sources:
        results["sources"]["github"] = search_github_repos(topic)

    results["total_results"] = sum(
        len(v) for v in results["sources"].values()
        if isinstance(v, list)
    )
    return results

if __name__ == "__main__":
    args = sys.argv[1:]
    sources = None
    for a in args:
        if a.startswith("--sources="):
            sources = a.split("=")[1].split(",")

    topic = sys.stdin.read().strip()
    if not topic:
        print(json.dumps({"error": "no topic"}))
        sys.exit(1)

    results = fetch_all(topic, sources)
    print(json.dumps({
        "technique": "knowledge_pipeline",
        "source": "ArXiv, SemanticScholar, GitHub APIs",
        "tier_bridge": 0.15,
        "results": results,
        "instruction": "Incorporate relevant findings. Cite specific papers/repos."
    }, indent=2))
