"""
Tests for dag-router.py — compact format, fast path, keyword matching.
Run: pytest tests/test_dag_router.py -v
"""
import json
import os
import sys
import tempfile
from pathlib import Path

# Add scripts dir to path
SCRIPTS = Path(__file__).parent.parent / "skills" / "intelligence-engine" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from importlib.machinery import SourceFileLoader

dr = SourceFileLoader("dag_router", str(SCRIPTS / "dag-router.py")).load_module()


class TestAbbrevDag:
    def test_hyphenated(self):
        assert dr.abbrev_dag("deepsuck-harness") == "dh"
        assert dr.abbrev_dag("collar-harness") == "ch"

    def test_underscored(self):
        assert dr.abbrev_dag("dag_harness") == "dh"

    def test_single_word(self):
        assert dr.abbrev_dag("leash") == "lea"
        assert dr.abbrev_dag("memory") == "mem"


class TestAbbrevVerb:
    def test_short_verbs_unchanged(self):
        assert dr.abbrev_verb("refer") == "refer"
        assert dr.abbrev_verb("impl") == "impl"
        assert dr.abbrev_verb("polls") == "polls"

    def test_long_verbs_abbreviated(self):
        assert dr.abbrev_verb("references") == "refer"
        assert dr.abbrev_verb("implements") == "imple"
        assert dr.abbrev_verb("routes_through") == "route"
        assert dr.abbrev_verb("wired_through") == "wired"

    def test_unknown_truncated(self):
        assert dr.abbrev_verb("complicated_verb") == "compl"


class TestCompactCard:
    def test_standard_cards(self):
        assert dr.compact_card("1:1") == "11"
        assert dr.compact_card("1:N") == "1N"
        assert dr.compact_card("1:many") == "1m"
        assert dr.compact_card("many:many") == "mm"

    def test_any_wildcard(self):
        assert dr.compact_card("any:any") == "**"  # : replaced, any→*


class TestLoadCompact:
    def test_plain_text_dag(self, tmp_path):
        """Plain-text .dag files (built-in DAGs) are read directly."""
        dag = tmp_path / "memory.dag"
        dag.write_text("[memory]\nSave→ Facts:durable(11)\n")
        blocks = dr.load_compact(roots=[str(tmp_path)])
        assert len(blocks) >= 1
        names = [b[0] for b in blocks]
        assert "memory" in names

    def test_json_dag_with_compact(self, tmp_path):
        """JSON .dag with compact field is extracted."""
        dag = tmp_path / "test.dag"
        data = {
            "v": 2,
            "p": "test",
            "n": [],
            "compact": "[te]\nEntity→Target:verb(11)",
        }
        dag.write_text(json.dumps(data))
        blocks = dr.load_compact(roots=[str(tmp_path)])
        assert len(blocks) >= 1
        assert blocks[0][1].startswith("[te]")

    def test_json_dag_empty_compact_skipped(self, tmp_path):
        """JSON .dag with empty compact (no newline) is skipped."""
        dag = tmp_path / "empty.dag"
        data = {"v": 2, "p": "empty", "n": [], "compact": "[em]"}
        dag.write_text(json.dumps(data))
        blocks = dr.load_compact(roots=[str(tmp_path)])
        names = [b[0] for b in blocks]
        assert "empty" not in names

    def test_large_json_dag(self, tmp_path):
        """JSON .dag over 4KB still loads (regression test for 256KB limit)."""
        dag = tmp_path / "large.dag"
        # Create a JSON file > 4KB with compact field
        padding = "x" * 5000
        data = {
            "v": 2,
            "p": "large",
            "n": [{"i": padding, "t": "entity", "es": []}],
            "compact": "[la]\nEntity→Target:verb(11)",
        }
        dag.write_text(json.dumps(data))
        blocks = dr.load_compact(roots=[str(tmp_path)])
        assert len(blocks) >= 1
        assert blocks[0][1].startswith("[la]")


class TestMatchCompact:
    def test_keyword_match(self):
        blocks = [("memory", "[memory]\nSave→ Facts:durable(11)")]
        result = dr.match_compact("memory facts", blocks)
        assert "memory" in result
        assert "Facts" in result

    def test_no_match_returns_all(self):
        blocks = [("mem", "[mem]\nSave→ Facts:durable(11)")]
        result = dr.match_compact("xyz", blocks)
        assert "mem" in result  # falls back to all

    def test_empty_query_returns_all(self):
        blocks = [("a", "[a]\nX→Y:verb(11)"), ("b", "[b]\nZ→W:verb(11)")]
        result = dr.match_compact("", blocks)
        assert "[a]" in result
        assert "[b]" in result

    def test_short_keywords_filtered(self):
        """Keywords ≤ 2 chars are ignored."""
        blocks = [("test", "[te]\nSomeEntity→Target:verb(11)")]
        result = dr.match_compact("a b c", blocks)  # all ≤ 2 chars → all blocks
        assert "[te]" in result


class TestBuildCompact:
    def test_format_uses_arrow_separators(self):
        entities = [
            {"dag": "dh", "name": "Entity", "edges": ["Target:verb(11)"]},
        ]
        result = dr.build_compact(entities)
        assert "Entity→" in result
        assert "Target:verb(11)" in result
        # No old-style separators
        assert "◂" not in result
        # No [verb] brackets around verbs (header [dh] is fine)
        assert "[verb]" not in result
        assert "[" not in result.split("\n", 1)[1] if "\n" in result else True
        assert "!" not in result  # no required markers

    def test_multiple_edges_use_gt_separator(self):
        entities = [
            {"dag": "dh", "name": "Entity", "edges": ["A:verb(11)", "B:verb(1m)"]},
        ]
        result = dr.build_compact(entities)
        assert "A:verb(11)>B:verb(1m)" in result

    def test_dag_header_abbreviated(self):
        entities = [
            {"dag": "deepsuck-harness", "name": "Entity", "edges": ["X:verb(11)"]},
        ]
        result = dr.build_compact(entities)
        assert "[dh]" in result
        assert "[deepsuck-harness]" not in result


class TestEndToEnd:
    def test_main_compact_output(self, tmp_path, monkeypatch):
        """Full pipeline: dag file → compact output."""
        dag = tmp_path / "test.dag"
        data = {
            "v": 2,
            "p": "test",
            "n": [[0, "Entity", "entity", "", [], [], [[0, "verb", "1:1"]]]],
            "compact": "[te]\nEntity→Entity:verb(11)",
        }
        dag.write_text(json.dumps(data))

        # Override roots to only use tmp_path
        import dag_router as dr_mod
        monkeypatch.setattr(dr_mod, "KNOWN_ROOTS", [str(tmp_path)])

        # This is tricky — the module already imported. Use the function directly.
        blocks = dr.load_compact(roots=[str(tmp_path)])
        result = dr.match_compact("", blocks)
        assert "[te]" in result
        assert "Entity→Entity:verb(11)" in result
