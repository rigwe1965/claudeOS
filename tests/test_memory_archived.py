"""Archived (consolidated-away) memory entries must not be retrieved."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


def _write(ns, key, value, confidence=0.9):
    from memory import store
    from memory.schemas import MemoryEntryCreate
    return store.write(MemoryEntryCreate(
        namespace=ns, category="fact", key=key, value=value, confidence=confidence,
    ))


def _archive(entry_id):
    from core.database import get_db
    with get_db() as conn:
        conn.execute("UPDATE memory_entries SET archived=1 WHERE id=?", (entry_id,))


def test_list_entries_skips_archived(fresh_db):
    from memory import store
    keep = _write("acme", "plan.keep", "pricing tier gold")
    gone = _write("acme", "plan.gone", "pricing tier silver")
    _archive(gone.id)

    ids = {e.id for e in store.list_entries(namespace="acme")}
    assert keep.id in ids and gone.id not in ids

    ids = {e.id for e in store.list_entries(namespace="acme", include_archived=True)}
    assert gone.id in ids


def test_fts_search_skips_archived(fresh_db):
    from memory import store
    keep = _write("acme", "plan.keep", "zebra pricing")
    gone = _write("acme", "plan.gone", "zebra discount")
    _archive(gone.id)

    ids = {e.id for e in store.search_text("zebra", "acme")}
    assert ids == {keep.id}


def test_agent_context_skips_archived(fresh_db):
    from memory import store
    keep = _write("acme", "profile.keep", "kept", confidence=0.95)
    gone = _write("acme", "profile.gone", "archived", confidence=0.95)
    _archive(gone.id)

    ids = {e.id for e in store.get_context_for_agent("acme", min_confidence=0.85)}
    assert keep.id in ids and gone.id not in ids


def test_semantic_search_skips_archived(fresh_db):
    from memory import engine
    keep = _write("acme", "plan.keep", "alpha")
    gone = _write("acme", "plan.gone", "beta")
    _archive(gone.id)

    hits = [{"memory_id": gone.id}, {"memory_id": keep.id}]
    with patch.object(engine.vector_store, "search", return_value=hits):
        result = engine.search_semantic("anything", "acme")
    assert [e.id for e in result] == [keep.id]


def test_rewriting_archived_key_revives_it(fresh_db):
    from memory import store
    first = _write("acme", "plan.x", "old")
    _archive(first.id)

    again = _write("acme", "plan.x", "new")
    assert again.id == first.id
    assert [e.id for e in store.list_entries(namespace="acme")] == [first.id]
