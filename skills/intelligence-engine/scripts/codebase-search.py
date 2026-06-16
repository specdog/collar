#!/usr/bin/env python3
"""codebase-search.py — grep file CONTENTS for relevant code. Not just filenames."""
import sys, json, os, subprocess
from pathlib import Path

EXTS = ['*.py', '*.ts', '*.js', '*.yaml', '*.yml', '*.md', '*.dog']
SKIP_DIRS = '.git,node_modules,.venv,__pycache__,.dotdog-worktree,dist,build'
MAX_FILES = 8
MAX_LINES = 50

def search_codebase(query, roots=None):
    if roots is None:
        roots = [os.getcwd(), str(Path.home() / "deepsuck")]
    
    keywords = query.lower().split()
    if not keywords: return []
    
    results = []
    seen = set()
    
    for root in roots:
        if not os.path.isdir(root): continue
        
        for ext in EXTS:
            for kw in keywords[:3]:  # search top 3 keywords
                if len(kw) < 3: continue
                if len(results) >= MAX_FILES: break
                try:
                    r = subprocess.run(
                        ["grep", "-rl", "--include=" + ext, "-i", kw, root],
                        capture_output=True, text=True, timeout=10
                    )
                    for line in r.stdout.strip().split('\n'):
                        if len(results) >= MAX_FILES: break
                        if line and line not in seen:
                            seen.add(line)
                            snippet = read_snippet(line)
                            if snippet:
                                results.append({"path": line, "keyword": kw, "snippet": snippet})
                except: pass
    
    return results

def read_snippet(fpath, max_lines=MAX_LINES):
    try:
        with open(fpath, errors='ignore') as f:
            lines = [next(f).rstrip() for _ in range(max_lines) if True]
        return '\n'.join([l for l in lines if l.strip()][:max_lines])
    except: return ""

def format_for_injection(results):
    if not results: return ""
    lines = [f"\nCODEBASE ({len(results)} files):"]
    for r in results:
        lines.append(f"\n  {r['path']} (keyword: {r['keyword']})")
        lines.append("  " + "-"*40)
        for l in r['snippet'].split('\n')[:MAX_LINES]:
            lines.append(f"  {l}")
    return "\n".join(lines)

if __name__ == "__main__":
    query = sys.stdin.read().strip() if not sys.stdin.isatty() else " ".join(sys.argv[1:])
    if not query: print(json.dumps({"error": "no query"})); sys.exit(1)
    roots = [os.getcwd(), str(Path.home() / "deepsuck")]
    results = search_codebase(query, roots)
    if '--json' in sys.argv:
        print(json.dumps({"files": len(results), "results": results}, indent=2))
    else:
        print(format_for_injection(results))
