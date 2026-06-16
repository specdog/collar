# Knowledge Pipeline — API Integration Reference

Live research retrieval from open-access academic and code sources.
The internet is the training set. API-only inference, no local GPU needed.

## Source APIs

### 1. ArXiv XML API

- **Endpoint:** `http://export.arxiv.org/api/query`
- **Auth:** None required
- **Rate limit:** ~1 req/3s (gentleman's agreement, not enforced)
- **Format:** Atom XML response (parse with `xml.etree.ElementTree`)
- **Namespaces:** `atom="http://www.w3.org/2005/Atom"`

**Query parameters:**

| Param | Description | Example |
|-------|-------------|---------|
| `search_query` | Lucene query syntax: `all:term`, `ti:title`, `au:author` | `all:LLM+reasoning` |
| `start` | Pagination offset | `0` |
| `max_results` | Results per page (max ~100) | `5` |
| `sortBy` | `relevance`, `lastUpdatedDate`, `submittedDate` | `relevance` |
| `sortOrder` | `ascending`, `descending` | `descending` |

**Response parsing — Atom XML:**

```python
from xml.etree import ElementTree as ET
ns = {"atom": "http://www.w3.org/2005/Atom"}
root = ET.fromstring(response_bytes)
for entry in root.findall("atom:entry", ns):
    title = entry.find("atom:title", ns).text.strip()
    summary = entry.find("atom:summary", ns).text.strip()[:300]
    published = entry.find("atom:published", ns).text[:10]
    authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
    url = entry.find("atom:id", ns).text
```

**Gotcha:** ArXiv API returns Atom XML, not JSON. Must use XML parser. Response is UTF-8 encoded bytes — decode before parsing.

### 2. Semantic Scholar REST API

- **Endpoint:** `https://api.semanticscholar.org/graph/v1/paper/search`
- **Auth:** None required (anonymous tier)
- **Rate limit:** 100 req/5min (anonymous), 1000 req/5min (with API key)
- **Format:** JSON

**Query parameters:**

| Param | Description |
|-------|-------------|
| `query` | Search string |
| `limit` | Results per page (max 100) |
| `fields` | Comma-separated: `title,abstract,year,authors,url,citationCount,externalIds` |

**Response parsing:**

```python
r = data.get("data", [])
for p in r:
    title = p.get("title")
    abstract = (p.get("abstract") or "")[:300]
    year = p.get("year")
    authors = [a.get("name") for a in p.get("authors", [])]
    citations = p.get("citationCount", 0)
    url = p.get("url")
```

### 3. GitHub REST API (Search)

- **Endpoint:** `https://api.github.com/search/repositories`
- **Auth:** None required but heavily rate-limited without token
- **Rate limit:** 10 req/min (unauthenticated), 30 req/min (authenticated)
- **Format:** JSON

**Query parameters:**

| Param | Description |
|-------|-------------|
| `q` | Search query (URL-encoded) |
| `sort` | `stars`, `forks`, `updated` |
| `order` | `desc`, `asc` |
| `per_page` | Results per page (max 100) |

**Headers required:**

```
Accept: application/vnd.github.v3+json
User-Agent: IntelligenceEngine/1.0
```

**Rate limit handling:** GitHub returns `X-RateLimit-Remaining` header.
When 0, wait until `X-RateLimit-Reset` epoch timestamp. Without auth token,
expect ~10 requests then a block. Use `GITHUB_TOKEN` env var for higher limits.

## Integration Pattern

All three sources are queried in parallel in `knowledge-pipeline.py`:

```python
results = {
    "arxiv": search_arxiv(topic),
    "semantic_scholar": search_semantic_scholar(topic),
    "github": search_github_repos(topic)
}
```

Each search function handles its own errors and returns `[{"error": "..."}]`
on failure — the pipeline never crashes on one source failure.

## Usage

```bash
# All sources
echo "LLM reasoning techniques" | python3 knowledge-pipeline.py

# Specific sources only
echo "graph neural networks" | python3 knowledge-pipeline.py --sources arxiv,github
```

## Pitfalls

- **ArXiv XML gotcha:** Returns Atom XML, NOT JSON. Must use ElementTree, not json.load().
- **GitHub anonymous rate limit:** ~10 req/min. Use token for persistent use.
- **Semantic Scholar corpus:** Focused on CS/engineering. Limited coverage outside STEM.
- **Timeout:** All requests have 15s timeout. Slow responses → empty result array (not crash).
- **ArXiv sortBy=relevance:** Requires at least 1 result or returns empty. Fall back to `sortBy=lastUpdatedDate` for very specific queries.
