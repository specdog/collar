from dag_cli import codex_broker


def test_local_read_short_circuit(tmp_path):
    sample = tmp_path / "README.md"
    sample.write_text("hello\nworld\n")
    out = codex_broker._read_file_prompt("read README.md", str(tmp_path))
    assert "README.md" in out
    assert "hello" in out


def test_cache_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(codex_broker, "_repo_fingerprint", lambda root: "fp")
    root = str(tmp_path)
    codex_broker._store_cached_response(root, "fix parser", "done")
    assert codex_broker._lookup_cached_response(root, "fix parser") == "done"


def test_relevant_file_resolution_prefers_explicit_paths(tmp_path):
    sample = tmp_path / "src.txt"
    sample.write_text("alpha\n")
    files = codex_broker._resolve_candidate_files(str(tmp_path), "check src.txt")
    assert str(sample) in files
