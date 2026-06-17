#!/usr/bin/env python3
"""DAG-compressed context injection. 95% fewer tokens than prose.
Converts entity graph to compact notation:
  EntityName(states){->Target(verb),->Target2(verb2)}
Replaces 3500+ char ground truth with ~200 char structured reference."""
import sys, json, os
from pathlib import Path

def compress_entities(entities, limit=50):
    """Compress entity list to minimal token representation."""
    lines = []
    for e in entities[:limit]:
        name = e.get("name","?")
        states = ",".join(e.get("states",[])[:4])
        edges = ",".join(
            f"→{ed['target']}({ed['verb'][:8]})" 
            for ed in e.get("edges",[])[:4]
        )
        line = f"{name}"
        if states: line += f"({states})"
        if edges: line += f"{{{edges}}}"
        lines.append(line)
    return "|".join(lines)

def compress_compact(entities, limit=50):
    """Ultra-compact: entity:states:edges format, no whitespace."""
    parts = []
    for e in entities[:limit]:
        states = ",".join(e.get("states",[])[:3])
        edges = ",".join(
            f"→{ed['target'][:10]}:{ed['verb'][:6]}" 
            for ed in e.get("edges",[])[:3]
        )
        parts.append(f"{e['name']}:{states}:{edges}" if edges else f"{e['name']}:{states}")
    return "|".join(parts)

if __name__ == "__main__":
    # Load entities from dag-router
    import subprocess
    dr = os.path.join(os.path.dirname(__file__), "dag-router.py")
    query = sys.stdin.read().strip() if not sys.stdin.isatty() else " ".join(sys.argv[1:])
    
    r = subprocess.run(["python3", dr, "--all"], capture_output=True, text=True, timeout=5)
    if r.returncode != 0:
        print("ERROR")
        sys.exit(1)
    
    data = json.loads(r.stdout)
    entities = data.get("entities", [])
    
    if "--ultra" in sys.argv:
        compressed = compress_compact(entities)
    else:
        compressed = compress_entities(entities)
    
    # Show savings
    prose = f"Entities loaded: {len(entities)}" + " ".join(
        f"{e['name']}({e.get('desc','')[:50]})" for e in entities[:20]
    )
    saving = int((1 - len(compressed)/len(prose)) * 100) if prose else 0
    
    if "--json" in sys.argv:
        print(json.dumps({
            "compressed": compressed,
            "chars": len(compressed),
            "prose_chars": len(prose),
            "savings_pct": saving,
            "entities": len(entities)
        }))
    else:
        print(compressed)
        print(f"\n[Saved: {len(prose)}→{len(compressed)} chars ({saving}%)]", file=sys.stderr)
