#!/usr/bin/env python3
"""Token-optimal DAG grounding. Query-matched only, 60-char descs, max 15 entities."""
import sys, json, os
from pathlib import Path

KNOWN_ROOTS = [
    os.getcwd(),
    str(Path.home() / "deepsuck" / "projects"),
    str(Path.home() / "projects"),
    str(Path.home() / "specdog" / "projects"),
]
SKIP_DAGS = {"deepsuck-harness"}
MAX_ENTITIES = 15
DESC_MAX = 60

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
    if isinstance(n, dict):
        name = str(n.get("i", n.get("id", "")))
        desc = str(n.get("d", n.get("desc", "")))
        typ = str(n.get("t", n.get("g", "")))
    elif isinstance(n, list):
        name = str(n[1]) if len(n) > 1 else ""
        desc = str(n[3]) if len(n) > 3 else ""
        typ = str(n[2]) if len(n) > 2 else ""
    else:
        return None
    # Skip predictions, empty names, states (no desc = noise)
    if not name or not desc or typ == "prediction":
        return None
    # Truncate description
    desc = desc[:DESC_MAX].rsplit(" ",1)[0] if len(desc) > DESC_MAX else desc
    return {"name": name, "desc": desc}

def load_entities(roots=None):
    dags = find_all_dags(roots)
    all_entities = []
    for dp in dags:
        try:
            with open(dp) as f: dag = json.load(f)
            pname = os.path.basename(dp).replace('.dag','')
            for n in dag.get("n", []):
                e = parse_node(n)
                if e:
                    e["dag"] = pname
                    all_entities.append(e)
        except: pass
    return all_entities

def match(query, entities):
    keywords = [kw.lower() for kw in query.lower().split() if len(kw) > 2]
    if not keywords:
        return entities[:MAX_ENTITIES]
    scored = []
    for e in entities:
        text = (e["name"] + " " + e["desc"]).lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scored.append((score, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored][:MAX_ENTITIES]

def build_compact(matched):
    if not matched:
        return ""
    lines = []
    cur = None
    for e in matched:
        if e["dag"] != cur:
            cur = e["dag"]
            lines.append(f"[{cur}]")
        lines.append(f"  {e['name']}: {e['desc']}")
    return "\n".join(lines)

if __name__ == "__main__":
    query = None
    for i,a in enumerate(sys.argv[1:]):
        if a == '--query' and i+2 < len(sys.argv):
            query = sys.argv[i+2]
    entities = load_entities()
    matched = match(query or "", entities)
    if '--all' in sys.argv:
        print(json.dumps({"total": len(entities), "matched": len(matched), "entities": matched}, indent=2))
    else:
        print(build_compact(matched))
