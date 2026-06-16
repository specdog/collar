#!/usr/bin/env python3
"""dag-router.py — multi-DAG grounding. Shows entities + ALL edges uncompressed."""
import sys, json, os
from pathlib import Path

KNOWN_ROOTS = [
    os.getcwd(),
    str(Path.home() / "deepsuck" / "projects"),
    str(Path.home() / "projects"),
    str(Path.home() / "specdog" / "projects"),
]
ALWAYS_INCLUDE = [
    str(Path.home() / "deepsuck" / "projects" / "deepsuck-harness" / "deepsuck-harness.dag"),
]

def find_all_dags(roots=None):
    roots = roots or KNOWN_ROOTS
    dags, seen = [], set()
    for p in ALWAYS_INCLUDE:
        if os.path.exists(p) and p not in seen: seen.add(p); dags.append(p)
    for root in roots:
        if not os.path.isdir(root): continue
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in {'.git','node_modules','.venv','__pycache__'} and not d.startswith('.')]
            if '.dotdog-worktree' in dirpath: continue
            for f in files:
                if f.endswith('.dag'):
                    p = os.path.join(dirpath, f)
                    if p not in seen: seen.add(p); dags.append(p)
    return dags

def load_all_entities(roots=None):
    dags = find_all_dags(roots)
    all_entities = []
    for dp in dags:
        try:
            with open(dp) as f: dag = json.load(f)
            pname = os.path.basename(dp).replace('.dag','')
            for n in dag.get("n", []):
                all_entities.append({
                    "dag": pname, "name": n.get("i","?"), "type": n.get("g","?"),
                    "desc": n.get("d","")[:200], "states": n.get("s",[]),
                    "lifecycle": n.get("l",[]),
                    "edges": [{"target":e.get("t","?"), "verb":e.get("v","?"), "card":e.get("c","?"), "required":e.get("r",False)} for e in n.get("es",[])]
                })
        except: pass
    return {"dags_found": len(dags), "entities": all_entities}

def search_entities(entities, query):
    keywords = [kw.lower() for kw in query.lower().split() if len(kw) > 2]
    if not keywords: return entities
    scored = []
    for e in entities:
        if "error" in e: continue
        text = (e.get("name","") + " " + e.get("desc","")).lower()
        score = sum(1 for kw in keywords if kw in text)
        if score > 0: scored.append((score, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    result = [e for _, e in scored]
    return result if result else entities

def build_ground_truth_string(entities, query=None, limit=50):
    if query: entities = search_entities(entities, query)
    lines = []
    dags_seen = set()
    for e in entities[:limit]: dags_seen.add(e.get("dag","?"))
    lines.append(f"GROUND TRUTH - {len(dags_seen)} DAG(s), {min(limit,len(entities))} entities:")
    current_dag = None
    for e in entities[:limit]:
        dag = e.get("dag","?")
        if dag != current_dag:
            current_dag = dag; lines.append(f"\n[{dag}]")
        lines.append(f"  {e['name']} ({e['type']}): {e['desc']}")
        if e.get('states'): lines.append(f"    States: {', '.join(e['states'])}")
        if e.get('lifecycle'): lines.append(f"    Lifecycle: {' -> '.join(e['lifecycle'])}")
        if e.get('edges'):
            lines.append(f"    Relationships:")
            for ed in e['edges']:
                req = "required" if ed.get('required') else "optional"
                lines.append(f"      -> {ed['target']} [{ed['verb']}] ({ed['card']}, {req})")
    return "\n".join(lines)

if __name__ == "__main__":
    query = None
    for i,a in enumerate(sys.argv[1:]):
        if a=='--query' and i+1<len(sys.argv): query = sys.argv[i+1]
    data = load_all_entities()
    if '--all' in sys.argv:
        print(json.dumps(data, indent=2))
    else:
        print(build_ground_truth_string(data["entities"], query))
