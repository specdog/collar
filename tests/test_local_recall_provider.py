from agent.local_recall_provider import LocalRecallProvider


def _fake_git_root(path: str) -> str:
    return path


def _fake_repo_fingerprint(path: str) -> str:
    return "repo-fp"


def test_exact_recall_prefetch_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setattr("agent.local_recall_provider._git_root", _fake_git_root)
    monkeypatch.setattr(
        "agent.local_recall_provider._repo_fingerprint", _fake_repo_fingerprint
    )

    provider = LocalRecallProvider()
    provider.initialize("sess-1", dag_home=str(tmp_path), cwd=str(tmp_path))
    provider.sync_turn(
        "How do we start the worker?",
        "Run `dag worker start` from the repo root.",
        session_id="sess-1",
        messages=[
            {"role": "user", "content": "How do we start the worker?"},
            {"role": "assistant", "content": "Run `dag worker start` from the repo root."},
        ],
    )

    block = provider.prefetch("How do we start the worker?")
    assert "LOCAL RECALL:" in block
    assert "dag worker start" in block


def test_tool_turns_do_not_enter_exact_cache(monkeypatch, tmp_path):
    monkeypatch.setattr("agent.local_recall_provider._git_root", _fake_git_root)
    monkeypatch.setattr(
        "agent.local_recall_provider._repo_fingerprint", _fake_repo_fingerprint
    )

    provider = LocalRecallProvider()
    provider.initialize("sess-1", dag_home=str(tmp_path), cwd=str(tmp_path))
    provider.sync_turn(
        "Fix the test",
        "Patched the file and ran the test.",
        session_id="sess-1",
        messages=[
            {"role": "user", "content": "Fix the test"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "1", "type": "function", "function": {"name": "exec"}}],
            },
            {"role": "tool", "tool_call_id": "1", "content": "ok"},
            {"role": "assistant", "content": "Patched the file and ran the test."},
        ],
    )

    assert provider.prefetch("Fix the test") == ""
