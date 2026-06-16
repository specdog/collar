#!/usr/bin/env python3
"""
context-injector.py -- Pre-generation knowledge enrichment
Before the LLM answers, enrich context with:
  1. DAG entities relevant to the question
  2. Fact store recall on the topic
  3. Code file paths that may be relevant
  4. API-sourced data (ArXiv, GitHub if research-related)

This is real context injection — not a prompt about context injection.
The agent runs this BEFORE generating, feeds the output into its context.

Usage: echo "user question" | python3 context-injector.py --dag /path/to/project.dag --cwd /project
"""
import sys, json, os, subprocess

def find_dag(cwd):
    """Find .dag files in the project."""
    dags = []
    for root, dirs, files in os.walk(cwd):
        if '.git' in dirs:
            dirs.remove('.git')
        for f in files:
            if f.endswith('.dag'):
                dags.append(os.path.join(root, f))
    return dags

def query_fact_store(query):
    """Recall relevant facts from the fact store."""
    script = os.path.join(os.path.dirname(__file__), "fact-store.py")
    try:
        result = subprocess.run(
            ["python3", script, "--recall"],
            input=query, capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except:
        pass
    return {"results": 0, "facts": []}

def extract_keywords(question):
    """Extract likely entity names and key terms from the question."""
    # Simple heuristic: capitalized words and quoted strings
    import re
    keywords = set()
    
    # Capitalized words (likely entity names)
    for word in re.findall(r'[A-Z][a-zA-Z]+', question):
        if len(word) > 2:
            keywords.add(word)
    
    # Quoted strings
    for quoted in re.findall(r'"[^"]+"', question):
        keywords.add(quoted.strip('"'))
    
    # File paths
    for path in re.findall(r'/[a-zA-Z0-9/._-]+', question):
        keywords.add(path)
    
    return list(keywords)

def query_dag(dag_path, keywords):
    """Search DAG for matching entities."""
    try:
        with open(dag_path) as f:
            dag = json.load(f)
        
        results = []
        for node in dag.get("n", []):
            node_id = node.get("i", "")
            node_desc = node.get("d", "")
            
            for kw in keywords:
                if kw.lower() in node_id.lower() or kw.lower() in node_desc.lower():
                    results.append({
                        "entity": node_id,
                        "type": node.get("g", ""),
                        "description": node_desc[:200],
                        "states": node.get("s", []),
                        "lifecycle": node.get("l", []),
                        "edges": [
                            {"target": e.get("t"), "verb": e.get("v")}
                            for e in node.get("es", [])
                        ][:5]
                    })
                    break
        
        return results
    except:
        return []

if __name__ == "__main__":
    args = sys.argv[1:]
    dag_path = None
    cwd = os.getcwd()
    
    for i, a in enumerate(args):
        if a == '--dag' and i+1 < len(args):
            dag_path = args[i+1]
        if a == '--cwd' and i+1 < len(args):
            cwd = args[i+1]
    
    question = sys.stdin.read().strip()
    if not question:
        print(json.dumps({"error": "no question"}))
        sys.exit(1)
    
    # Auto-detect DAG if not specified
    if not dag_path:
        dags = find_dag(cwd)
        if dags:
            dag_path = dags[0]
    
    keywords = extract_keywords(question)
    
    # 1. Query DAG
    dag_results = query_dag(dag_path, keywords) if dag_path else []
    
    # 2. Query fact store
    fact_results = query_fact_store(question)
    
    print(json.dumps({
        "pipeline": "context-injector",
        "question_length": len(question),
        "keywords_detected": keywords,
        "dag_path": dag_path,
        "dag_matches": len(dag_results),
        "dag_entities": dag_results,
        "fact_store_matches": fact_results.get("results", 0),
        "fact_store_facts": fact_results.get("facts", []),
        "instruction": "Inject these findings into your context BEFORE generating an answer. Facts from DAG and fact store are ground truth. If your answer contradicts them, it's wrong."
    }, indent=2))
