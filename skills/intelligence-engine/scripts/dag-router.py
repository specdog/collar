#!/usr/bin/env python3
"""DAG-path grounding with cross-DAG hop resolution. 1-hop max."""
import sys, json, os
from pathlib import Path

KNOWN_ROOTS = [
    os.getcwd(),
    str(Path.home() / "deepsuck" / "projects"),
    str(Path.home() / "projects"),
    str(Path.home() / "specdog" / "projects"),
]
SKIP_DAGS = {"deepsuck-harness"}
HARNESS_DAG = str(Path.home() / "deepsuck" / "projects" / "deepsuck-harness" / "deepsuck-harness.dag")
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

def load_edge_index(path):
    """Load a DAG file as {entity_name: [edge_strs]} for cross-DAG resolution."""
    idx = {}
    try:
        with open(path) as f: dag = json.load(f)
        nodes = dag.get("n", [])
        id_map = {}
        for n in nodes:
            if isinstance(n, list): id_map[n[0]] = n[1]
            elif isinstance(n, dict): id_map[n.get("i","")] = n.get("i","")
        for n in nodes:
            if isinstance(n, list) and len(n) > 6:
                name = n[1]
                edges = n[6] if isinstance(n[6], list) else []
                idx[name] = [(id_map.get(e[0], str(e[0])), str(e[1]), str(e[2])) for e in edges if isinstance(e, list) and len(e)>=3]
            elif isinstance(n, dict):
                name = n.get("i","")
                edges = n.get("es", [])
                idx[name] = [(e.get("t","?"), e.get("v",""), e.get("c","")) for e in edges]
    except: pass
    return idx

def format_edge(tgt, verb, card, required=False):
    req = "!" if required else ""
    return f"{tgt}[{verb}]({card}){req}"

def load_all(roots=None):
    harness_idx = load_edge_index(HARNESS_DAG)
    dags = find_all_dags(roots)
    all_entities = []
    for dp in dags:
        try:
            with open(dp) as f: dag = json.load(f)
            pname = os.path.basename(dp).replace('.dag','')
            nodes = dag.get("n", [])
            id_map = {}
            for n in nodes:
                if isinstance(n, list): id_map[n[0]] = n[1]
                elif isinstance(n, dict): id_map[n.get("i","")] = n.get("i","")
            for n in nodes:
                if isinstance(n, dict):
                    name = str(n.get("i",""))
                    typ = str(n.get("t", n.get("g", "")))
                    raw_edges = n.get("es", [])
                    if not name or typ in ("prediction", "state"): continue
                    edge_strs = []
                    for e in raw_edges:
                        tgt = e.get("t","?")
                        verb = e.get("v","")
                        card = e.get("c","?")
                        req = e.get("r", False)
                        edge_str = format_edge(tgt, verb, card, req)
                        # Cross-DAG resolution: if target is in harness index, chain 1 hop
                        if tgt in harness_idx and harness_idx[tgt]:
                            chain = ", ".join(f"{ct}[{cv}]" for ct, cv, cc in harness_idx[tgt][:3])
                            edge_str += f"▸{chain}"
                        edge_strs.append(edge_str)
                    all_entities.append({"dag": pname, "name": name, "edges": edge_strs})
                elif isinstance(n, list) and len(n) > 6:
                    name = str(n[1])
                    typ = str(n[2])
                    raw_edges = n[6] if isinstance(n[6], list) else []
                    if not name or typ in ("prediction", "state"): continue
                    edge_strs = []
                    for e in raw_edges:
                        if not isinstance(e, list) or len(e) < 3: continue
                        tgt = id_map.get(e[0], str(e[0]))
                        verb = str(e[1])
                        card = str(e[2])
                        req = e[3] if len(e) > 3 else False
                        edge_str = format_edge(tgt, verb, card, req)
                        if tgt in harness_idx and harness_idx[tgt]:
                            chain = ", ".join(f"{ct}[{cv}]" for ct, cv, cc in harness_idx[tgt][:3])
                            edge_str += f"▸{chain}"
                        edge_strs.append(edge_str)
                    if edge_strs:
                        all_entities.append({"dag": pname, "name": name, "edges": edge_strs})
        except: pass
    return all_entities

def match(query, entities):
    keywords = [kw.lower() for kw in query.lower().split() if len(kw) > 2]
    if not keywords:
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
    if not matched: return ""
    lines, cur = [], None
    for e in matched:
        if e["dag"] != cur:
            cur = e["dag"]
            lines.append(f"[{cur}]")
        edge_str = ", ".join(e["edges"])
        lines.append(f"  {e['name']} ◂ {edge_str}" if edge_str else f"  {e['name']}")
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
