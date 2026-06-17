#!/usr/bin/env python3
"""DAG-path grounding. Shows relationships, not prose descriptions."""
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

def load_all(roots=None):
    """Returns (entities, id_map) where entities have resolved edge names."""
    dags = find_all_dags(roots)
    all_entities = []
    for dp in dags:
        try:
            with open(dp) as f: dag = json.load(f)
            pname = os.path.basename(dp).replace('.dag','')
            nodes = dag.get("n", [])
            
            # Build id→name map (for array format)
            id_map = {}
            for n in nodes:
                if isinstance(n, list) and len(n) > 1:
                    id_map[n[0]] = n[1]
                elif isinstance(n, dict):
                    id_map[n.get("i", n.get("id",""))] = n.get("i", n.get("id",""))
            
            for n in nodes:
                name, edges = parse_node(n, id_map)
                if name and edges:
                    all_entities.append({"dag": pname, "name": name, "edges": edges})
        except: pass
    return all_entities

def parse_node(n, id_map):
    """Extract name + resolved edge strings. Returns (name, [edge_strs]) or (None, [])."""
    if isinstance(n, dict):
        name = str(n.get("i", n.get("id", "")))
        typ = str(n.get("t", n.get("g", "")))
        raw_edges = n.get("es", [])
        if not name or typ in ("prediction", "state"): return (None, [])
        edge_strs = []
        for e in raw_edges:
            tgt = e.get("t", "?")
            verb = e.get("v", "")
            card = e.get("c", "?")
            req = "!" if e.get("r") else ""
            edge_strs.append(f"{tgt}[{verb}]({card}){req}")
        return (name, edge_strs)
    
    elif isinstance(n, list):
        name = str(n[1]) if len(n) > 1 else ""
        typ = str(n[2]) if len(n) > 2 else ""
        raw_edges = n[6] if len(n) > 6 and isinstance(n[6], list) else []
        if not name or typ in ("prediction", "state"): return (None, [])
        edge_strs = []
        for e in raw_edges:
            if isinstance(e, list) and len(e) >= 3:
                tgt_id = e[0]
                verb = str(e[1])
                card = str(e[2])
                req = "!" if len(e) > 3 and e[3] else ""
                tgt_name = id_map.get(tgt_id, str(tgt_id))
                edge_strs.append(f"{tgt_name}[{verb}]({card}){req}")
        return (name, edge_strs)
    
    return (None, [])

def match(query, entities):
    keywords = [kw.lower() for kw in query.lower().split() if len(kw) > 2]
    if not keywords:
        # Return edge-bearing entities first
        return [e for e in entities if e["edges"]][:MAX_ENTITIES]
    scored = []
    for e in entities:
        text = e["name"].lower() + " " + " ".join(e["edges"]).lower()
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
        edge_str = ", ".join(e["edges"])
        lines.append(f"  {e['name']} → {edge_str}" if edge_str else f"  {e['name']}")
    return "\n".join(lines)

if __name__ == "__main__":
    query = None
    for i,a in enumerate(sys.argv[1:]):
        if a == '--query' and i+2 < len(sys.argv):
            query = sys.argv[i+2]
    entities = load_all()
    matched = match(query or "", entities)
    if '--all' in sys.argv:
        print(json.dumps({"total": len(entities), "matched": len(matched), "entities": matched}, indent=2))
    else:
        print(build_compact(matched))
