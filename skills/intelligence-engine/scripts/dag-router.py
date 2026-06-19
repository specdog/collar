#!/usr/bin/env python3
"""DAG-path grounding — compact, no self-loops, 4-edge cap, resolved hops."""
import sys, json, os
from pathlib import Path

KNOWN_ROOTS = [
    os.getcwd(),
    str(Path.home() / "dag" / "projects"),
    str(Path.home() / "projects"),
    str(Path.home() / "specdog" / "projects"),
]
SKIP_DAGS = {"dag-harness"}
HARNESS_DAG = str(Path.home() / "dag" / "projects" / "dag-harness" / "dag-harness.dag")
MAX_ENTITIES = 15
MAX_EDGES = 5

def compact_card(card):
    """1:N→1N, many:many→mm, 1:many→1m, N:M→NM, N:1→N1, 1:1→11"""
    c = card.replace(":", "").replace("many", "m").replace("any", "*")
    return c if len(c) <= 3 else card[:4]

def card_rank(card):
    """Lower = more specific. 1:1 best, mm worst."""
    if "1:1" in card or "11" in card: return 0
    if "1:N" in card or "1N" in card or "1:m" in card or "1m" in card: return 1
    if "N:1" in card or "N1" in card or "m:1" in card: return 2
    if "N:M" in card or "NM" in card: return 3
    if "m:m" in card or "mm" in card: return 4
    return 5

def abbrev_dag(name):
    """Abbreviate DAG name for compact headers: deepsuck-harness→dh, collar-harness→ch"""
    parts = name.replace('-',' ').replace('_',' ').split()
    if len(parts) >= 2:
        return ''.join(p[0] for p in parts[:2])
    return name[:3]

def abbrev_verb(verb):
    """Abbreviate verb to 5 chars max for token savings."""
    if len(verb) <= 5:
        return verb
    # Common abbreviations
    abbr = {'references':'refer','implements':'imple','routes_through':'route',
            'produces':'produ','refreshes':'refre','validates':'valid',
            'triggers':'trig','complements':'compl','executes':'execu',
            'queries':'queri','wired_through':'wired','polls':'polls'}
    return abbr.get(verb, verb[:5])

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
                raw = n[6] if isinstance(n[6], list) else []
                idx[name] = [(id_map.get(e[0], str(e[0])), str(e[1]), str(e[2])) for e in raw if isinstance(e, list) and len(e)>=3]
            elif isinstance(n, dict):
                name = n.get("i","")
                raw = n.get("es", [])
                idx[name] = [(e.get("t","?"), e.get("v",""), e.get("c","")) for e in raw]
    except: pass
    return idx

def load_compact(roots=None):
    """Fast path: read pre-built compact text from .dag files.
    Handles both JSON .dag (extracts 'compact' field) and plain-text .dag (uses directly)."""
    dags = find_all_dags(roots)
    blocks = []  # [(dag_name, compact_text)]
    for dp in dags:
        try:
            with open(dp) as f:
                raw = f.read(262144)  # 256KB — enough for any .dag
            # Try JSON first (dotdog-compiled .dag with compact field)
            if raw.strip().startswith('{'):
                dag = json.loads(raw)
                compact = dag.get("compact", "")
                if compact and '\n' in compact:
                    pname = os.path.basename(dp).replace('.dag','')
                    blocks.append((pname, compact))
            else:
                # Plain-text .dag — already in compact format
                text = raw.strip()
                if text and '\n' in text:
                    pname = os.path.basename(dp).replace('.dag','')
                    blocks.append((pname, text))
        except: pass
    return blocks

def match_compact(query, blocks, max_chars=4000):
    """Keyword match against pre-built compact blocks. Returns concatenated text.
    If no keywords match, returns all blocks (better context than nothing)."""
    keywords = [kw.lower() for kw in (query or "").lower().split() if len(kw) > 2]
    if not keywords:
        return "\n".join(b[1] for b in blocks)
    matched = []
    for pname, text in blocks:
        if any(kw in text.lower() for kw in keywords):
            matched.append(text)
    if not matched:
        # No keyword hits — return all to avoid empty context
        return "\n".join(b[1] for b in blocks)
    return "\n".join(matched)

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
                name, edges = parse_node(n, id_map, harness_idx)
                if name and edges:
                    all_entities.append({"dag": pname, "name": name, "edges": edges})
        except: pass
    return all_entities

def parse_node(n, id_map, harness_idx):
    """Extract name + sorted/capped edge strings. Drops self-loops."""
    if isinstance(n, dict):
        name = str(n.get("i",""))
        typ = str(n.get("t", n.get("g", "")))
        raw = n.get("es", [])
        if not name or typ in ("prediction", "state"): return (None, [])
        return (name, build_edges(name, raw, id_map, harness_idx, is_dict=True))
    elif isinstance(n, list) and len(n) > 6:
        name = str(n[1])
        typ = str(n[2])
        raw = n[6] if isinstance(n[6], list) else []
        if not name or typ in ("prediction", "state"): return (None, [])
        return (name, build_edges(name, raw, id_map, harness_idx, is_dict=False))
    return (None, [])

def build_edges(entity_name, raw_edges, id_map, harness_idx, is_dict):
    edge_tuples = []
    for e in raw_edges:
        if is_dict:
            tgt = e.get("t","?")
            verb = e.get("v","")
            card = e.get("c","?")
            req = e.get("r", False)
        else:
            if not isinstance(e, list) or len(e) < 3: continue
            tgt = id_map.get(e[0], str(e[0]))
            verb = str(e[1])
            card = str(e[2])
            req = e[3] if len(e) > 3 else False
        
        # Drop self-loops
        if tgt == entity_name: continue
        
        c = compact_card(card)
        edge_tuples.append((tgt, verb, c, req))
    
    # Sort: required first by specificity, then optional by specificity
    required = [e for e in edge_tuples if e[3]]
    optional = [e for e in edge_tuples if not e[3]]
    required.sort(key=lambda x: card_rank(x[2]))
    optional.sort(key=lambda x: card_rank(x[2]))
    
    # Always keep required edges, fill rest with best optional. Cap at MAX_EDGES.
    slots = MAX_EDGES - len(required)
    edge_tuples = required + optional[:max(0, slots)]
    if len(edge_tuples) > MAX_EDGES:
        edge_tuples = edge_tuples[:MAX_EDGES]
    
    # Format with cross-DAG resolution (compact: verb→5chars, no [] brackets)
    edge_strs = []
    for tgt, verb, card, req in edge_tuples:
        req_mark = ""  # Drop ! — agent doesn't need it, saves tokens
        abbrev = abbrev_verb(verb)
        edge_str = f"{tgt}:{abbrev}({card})"
        # Cross-DAG hop
        if tgt in harness_idx and harness_idx[tgt]:
            chain = ">".join(f"{ct}:{abbrev_verb(cv)}" for ct, cv, cc in harness_idx[tgt][:3])
            edge_str += f"▸{chain}"
        edge_strs.append(edge_str)
    
    return edge_strs

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
    """Token-optimized compact format. Separators: → entity→edge, > between edges."""
    if not matched: return ""
    lines, cur = [], None
    for e in matched:
        if e["dag"] != cur:
            cur = e["dag"]
            lines.append(f"[{abbrev_dag(cur)}]")
        edge_str = ">".join(e["edges"])
        lines.append(f"{e['name']}→{edge_str}" if edge_str else e['name'])
    return "\n".join(lines)

if __name__ == "__main__":
    query = None
    for i,a in enumerate(sys.argv[1:]):
        if a == '--query' and i+2 < len(sys.argv):
            query = sys.argv[i+2]
    # Fast path: use pre-built compact from dotdog compiled .dag files
    blocks = load_compact()
    if blocks:
        result = match_compact(query or "", blocks)
        # Cap at 4000 chars to prevent context blow-up
        if len(result) > 4000:
            result = result[:4000]
        if '--all' in sys.argv:
            print(json.dumps({"total": len(blocks), "matched": len(result.split('\n')), "compact": result}, indent=2))
        else:
            print(result)
    else:
        # Fallback: full JSON parse for .dag files without compact field
        entities = load_all()
        matched = match(query or "", entities)
        if '--all' in sys.argv:
            print(json.dumps({"total": len(entities), "matched": len(matched), "entities": matched}, indent=2))
        else:
            print(build_compact(matched))
