"""Built-in local recall provider.

Cheap, file-backed exact-turn memoization plus optional zero-LLM session
search for explicit recall-style queries. This provider is always safe to run:
it never makes network calls, never mutates the system prompt mid-session, and
coexists with one external memory provider under MemoryManager.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider
from utils import atomic_json_write

logger = logging.getLogger(__name__)

_MAX_CACHE_ENTRIES = 256
_MAX_ANSWER_CHARS = 2400
_MAX_PREFETCH_CHARS = 1600
_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
_RECALL_QUERY_RE = re.compile(
    r"\b("
    r"remember|recall|previous|earlier|before|last time|what did|"
    r"how did|which file|where did|search session|past session"
    r")\b",
    re.IGNORECASE,
)


def _normalize_query(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", (text or "").strip().lower())
    return collapsed[:400]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _run(cmd: list[str], cwd: Optional[str] = None) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return 127, ""
    out = proc.stdout.strip()
    err = proc.stderr.strip()
    if out and err:
        return proc.returncode, out + "\n" + err
    return proc.returncode, out or err


def _git_root(path: str) -> str:
    code, out = _run(["git", "-C", path, "rev-parse", "--show-toplevel"])
    if code == 0 and out:
        return out.splitlines()[0]
    return path


def _repo_fingerprint(path: str) -> str:
    root = _git_root(path)
    head_code, head = _run(["git", "-C", root, "rev-parse", "HEAD"])
    status_code, status = _run(["git", "-C", root, "status", "--short"])
    payload = "\n".join(
        [
            root,
            head if head_code == 0 else "",
            status if status_code == 0 else "",
        ]
    )
    return _sha(payload)


class LocalRecallProvider(MemoryProvider):
    """Always-on local recall provider with exact-turn memoization."""

    @property
    def name(self) -> str:
        return "builtin"

    def __init__(self) -> None:
        self._session_id = ""
        self._dag_home = Path.home() / ".dag"
        self._cwd = os.getcwd()
        self._cache_path = self._dag_home / "cache" / "local_recall.json"
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._session_db = None

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        self._session_id = session_id
        self._dag_home = Path(str(kwargs.get("dag_home") or self._dag_home))
        self._cwd = str(kwargs.get("cwd") or self._cwd)
        self._cache_path = self._dag_home / "cache" / "local_recall.json"
        self._session_db = kwargs.get("session_db")
        self._load_cache()

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return []

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        norm = _normalize_query(query)
        if len(norm) < 8:
            return ""

        exact = self._lookup_exact(norm)
        if exact:
            answer = str(exact.get("assistant") or "")[:_MAX_PREFETCH_CHARS]
            if answer:
                return (
                    "LOCAL RECALL:\n"
                    "Exact prior answer for the same workspace state and request:\n"
                    f"{answer}"
                )

        if not _RECALL_QUERY_RE.search(query or ""):
            return ""

        rows = self._search_sessions(norm)
        if not rows:
            return ""

        parts = ["SESSION RECALL:"]
        for row in rows[:2]:
            snippet = str(row.get("snippet") or row.get("content") or "").strip()
            if not snippet:
                continue
            snippet = re.sub(r"\s+", " ", snippet)[:320]
            parts.append(
                f"- {row.get('role') or 'message'} in session {row.get('session_id')}: {snippet}"
            )
        return "\n".join(parts)[:_MAX_PREFETCH_CHARS]

    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
        messages: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        norm = _normalize_query(user_content)
        answer = (assistant_content or "").strip()
        if len(norm) < 8 or not answer:
            return
        if messages and _turn_used_tools(messages):
            return

        try:
            repo_fp = _repo_fingerprint(self._cwd)
        except Exception:
            repo_fp = _sha(self._cwd)

        key = _sha(f"{self._cwd}\n{repo_fp}\n{norm}")
        self._cache[key] = {
            "query": norm,
            "assistant": answer[:_MAX_ANSWER_CHARS],
            "cwd": self._cwd,
            "repo_fp": repo_fp,
            "session_id": session_id or self._session_id,
            "ts": time.time(),
        }
        self._prune_cache()
        self._save_cache()

    def on_session_switch(
        self,
        new_session_id: str,
        *,
        parent_session_id: str = "",
        reset: bool = False,
        rewound: bool = False,
        **kwargs,
    ) -> None:
        self._session_id = new_session_id

    def _lookup_exact(self, norm_query: str) -> Optional[Dict[str, Any]]:
        try:
            repo_fp = _repo_fingerprint(self._cwd)
        except Exception:
            repo_fp = _sha(self._cwd)
        key = _sha(f"{self._cwd}\n{repo_fp}\n{norm_query}")
        entry = self._cache.get(key)
        if not entry:
            return None
        if (time.time() - float(entry.get("ts") or 0)) > _CACHE_TTL_SECONDS:
            self._cache.pop(key, None)
            return None
        return entry

    def _search_sessions(self, norm_query: str) -> List[Dict[str, Any]]:
        db = self._session_db
        if db is None:
            try:
                from dag_state import SessionDB

                db = SessionDB(
                    db_path=self._dag_home / "state.db",
                    read_only=True,
                )
            except Exception:
                logger.debug("local recall: failed to open state.db", exc_info=True)
                return []
        try:
            return db.search_messages(norm_query, limit=2, sort="newest") or []
        except Exception:
            logger.debug("local recall: session search failed", exc_info=True)
            return []

    def _load_cache(self) -> None:
        try:
            raw = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            self._cache = {}
            return
        self._cache = raw if isinstance(raw, dict) else {}
        self._prune_cache()

    def _save_cache(self) -> None:
        try:
            atomic_json_write(
                self._cache_path,
                self._cache,
                indent=2,
                sort_keys=True,
            )
        except Exception:
            logger.debug("local recall: cache write failed", exc_info=True)

    def _prune_cache(self) -> None:
        now = time.time()
        items = [
            (key, value)
            for key, value in self._cache.items()
            if isinstance(value, dict)
            and (now - float(value.get("ts") or 0)) <= _CACHE_TTL_SECONDS
        ]
        items.sort(key=lambda item: float(item[1].get("ts") or 0), reverse=True)
        self._cache = dict(items[:_MAX_CACHE_ENTRIES])


def _turn_used_tools(messages: List[Dict[str, Any]]) -> bool:
    last_user_idx = -1
    for idx, msg in enumerate(messages):
        if msg.get("role") == "user":
            last_user_idx = idx
    if last_user_idx < 0:
        return False
    for msg in messages[last_user_idx + 1:]:
        if msg.get("role") == "tool":
            return True
        if msg.get("tool_calls"):
            return True
    return False

