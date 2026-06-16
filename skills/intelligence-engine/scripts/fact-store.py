#!/usr/bin/env python3
"""
fact-store.py -- Real external memory (not simulated MemGPT pages)
Stores verified facts to disk. Retrieves relevant facts by topic.
Facts survive across sessions. This IS the memory, not a prompt about memory.

Usage:
  echo "fact text" | python3 fact-store.py --store --topic "topic" --source "DAG"
  echo "query" | python3 fact-store.py --recall
  python3 fact-store.py --list-topics
  python3 fact-store.py --stats
"""
import sys, json, os, hashlib
from datetime import datetime

FACT_DIR = os.path.expanduser("~/.deepsuck/intel-reports/facts")
os.makedirs(FACT_DIR, exist_ok=True)
FACT_DB = os.path.join(FACT_DIR, "fact-db.json")

def load_db():
    if os.path.exists(FACT_DB):
        with open(FACT_DB) as f:
            return json.load(f)
    return {"facts": [], "topics": {}, "stats": {"total_facts": 0, "verified": 0, "refuted": 0}}

def save_db(db):
    with open(FACT_DB, "w") as f:
        json.dump(db, f, indent=2)

def store_fact(text, topic, source="manual", verified=True):
    db = load_db()
    fact_id = hashlib.sha256(text.encode()).hexdigest()[:12]
    
    # Check for duplicates
    for f in db["facts"]:
        if f["id"] == fact_id:
            f["recalled_count"] = f.get("recalled_count", 0) + 1
            f["last_recalled"] = datetime.utcnow().isoformat() + "Z"
            save_db(db)
            return {"status": "duplicate", "id": fact_id, "recalled_count": f["recalled_count"]}
    
    fact = {
        "id": fact_id,
        "text": text[:500],
        "topic": topic,
        "source": source,
        "verified": verified,
        "stored_at": datetime.utcnow().isoformat() + "Z",
        "last_recalled": None,
        "recalled_count": 0
    }
    
    db["facts"].append(fact)
    db["stats"]["total_facts"] += 1
    if verified:
        db["stats"]["verified"] += 1
    
    if topic not in db["topics"]:
        db["topics"][topic] = []
    db["topics"][topic].append(fact_id)
    
    save_db(db)
    return {"status": "stored", "id": fact_id, "topic": topic}

def recall_facts(query, limit=10):
    """Simple keyword-based recall. Returns relevant facts sorted by recency."""
    db = load_db()
    query_lower = query.lower()
    keywords = query_lower.split()
    
    scored = []
    for fact in db["facts"]:
        fact_lower = (fact["text"] + " " + fact["topic"]).lower()
        score = sum(1 for kw in keywords if kw in fact_lower)
        if score > 0:
            scored.append((score, fact))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, fact in scored[:limit]:
        fact["recalled_count"] = fact.get("recalled_count", 0) + 1
        fact["last_recalled"] = datetime.utcnow().isoformat() + "Z"
        results.append(fact)
    
    if results:
        save_db(db)
    
    return results

def list_topics():
    db = load_db()
    topics = {}
    for topic, fact_ids in db["topics"].items():
        topics[topic] = len(fact_ids)
    return topics

def stats():
    db = load_db()
    return {
        "total_facts": db["stats"]["total_facts"],
        "verified": db["stats"]["verified"],
        "refuted": db["stats"]["refuted"],
        "topics": len(db["topics"]),
        "db_size_bytes": os.path.getsize(FACT_DB) if os.path.exists(FACT_DB) else 0
    }

if __name__ == "__main__":
    args = sys.argv[1:]
    
    if "--store" in args:
        text = sys.stdin.read().strip()
        topic = "general"
        source = "manual"
        for a in args:
            if a.startswith("--topic"):
                if "=" in a:
                    topic = a.split("=", 1)[1]
                else:
                    idx = args.index(a)
                    if idx+1 < len(args): topic = args[idx+1]
            if a.startswith("--source"):
                if "=" in a:
                    source = a.split("=", 1)[1]
                else:
                    idx = args.index(a)
                    if idx+1 < len(args): source = args[idx+1]
        result = store_fact(text, topic, source)
        print(json.dumps(result, indent=2))
    
    elif "--recall" in args:
        query = sys.stdin.read().strip()
        results = recall_facts(query)
        print(json.dumps({
            "query": query,
            "results": len(results),
            "facts": results
        }, indent=2))
    
    elif "--list-topics" in args:
        print(json.dumps(list_topics(), indent=2))
    
    elif "--stats" in args:
        print(json.dumps(stats(), indent=2))
    
    else:
        print(json.dumps({
            "usage": "fact-store.py --store | --recall | --list-topics | --stats",
            "description": "Real external memory for verified facts"
        }, indent=2))
