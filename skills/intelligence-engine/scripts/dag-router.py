#!/usr/bin/env python3
"""Minimal DAG grounding. Compact output. Skips harness self-description."""
import sys, json, os
from pathlib import Path

KNOWN_ROOTS = [
    os.getcwd(),
    str(Path.home() / "deepsuck" / "projects"),
    str(Path.home() / "projects"),
    str(Path.home() / "specdog" / "projects"),
]
# Harness describes enforcement internals — hooks handle that at code level.
# Skip it from ground truth to avoid self-referential noise.
SKIP_DAGS = {"deepsuck-harness"}

def find_all_dags(roots=None):
    roots = roots or KNOWN_ROOTS
    dags, seen = [], set()
    for root in roots:
        if not os.path.isdir(root): continue
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in {'.git','node_modules','.venv','__pycache__'} and not d.startswith('.')]
            if '.dotdog-worktree' in dirpath: continue
            for f in files:
                if f.endswith('.dag'):
                    p = os.path.join(dirpath, f)
                    pname = os.path.basename(p).replace('.dag','')
                    if pname in SKIP_DAGS: continue
                    if p not in seen: seen.add(p); dags.append(p)
    return dags

def parse_node(n):
    """Handle both array and dict DAG node formats."""
    if isinstance(n, dict):
        return {
            "name": n.get("i", n.get("id", "?")),
            "type": n.get("t", n.get("g", "?")),
            "desc": str(n.get("d", n.get("desc", "")))[:120],
            "state": (n.get("s", n.get("state", [])) or ["unknown"])[0] if isinstance(n.get("s", n.get("state", [])), list) else str(n.get("s", n.get("state", "unknown"))),
        }
    elif isinstance(n, list):
        return {
            "name": n[1] if len(n) > 1 else "?",
            "type": n[2] if len(n) > 2 else "?",
            "desc": str(n[3])[:120] if len(n) > 3 else "",
            "state": (n[4][0] if isinstance(n[4], list) and n[4] else "unknown") if len(n) > 4 and n[4] else "unknown",
        }
    return {"name": "?", "type": "?", "desc": "", "state": "unknown"}

def load_all_entities(roots=None):
    dags = find_all_dags(roots)
    all_entities = []
    for dp in dags:
        try:
            with open(dp) as f: dag = json.load(f)
            pname = os.path.basename(dp).replace('.dag','')
            for n in dag.get("n", []):
                e = parse_node(n)
                e["dag"] = pname
                all_entities.append(e)
        except: pass
    return {"dags_found": len(dags), "entities": all_entities}

def search_entities(entities, query):
    keywords = [kw.lower() for kw in query.lower().split() if len(kw) > 2]
    if not keywords: return entities
    scored = []
    for e in entities:
        text = (e.get("name","") + " " + e.get("desc","")).lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0: scored.append((score, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    result = [e for _, e in scored]
    return result if result else entities

def build_compact(entities, query=None, limit=50):
    if query:
        matched = search_entities(entities, query)
        matched_names = {e['name'] for e in matched}
        rest = [e for e in entities if e['name'] not in matched_names]
        entities = matched[:limit] + rest[:(limit - len(matched))]
    lines = []
    current_dag = None
    for e in entities[:limit]:
        dag = e.get("dag","?")
        if dag != current_dag:
            current_dag = dag
            lines.append(f"[{dag}]")
        lines.append(f"  {e['name']}: {e['desc']}")
    return "\n".join(lines)

if __name__ == "__main__":
    query = None
    for i,a in enumerate(sys.argv[1:]):
        if a=='--query' and i+1<len(sys.argv): query = sys.argv[i+1]
    data = load_all_entities()
    if '--all' in sys.argv:
        print(json.dumps(data, indent=2))
    else:
        print(build_compact(data["entities"], query))
