"""Semantic search must not hydrate memories from another namespace, even if a vector hit names one."""
from memory import engine, store
from memory.schemas import MemoryEntryCreate


def test_search_semantic_ignores_foreign_namespace_hits(fresh_db, monkeypatch):
    # 'team-a' and 'team_a' share a ChromaDB collection name (hyphen -> underscore)
    own = store.write(MemoryEntryCreate(namespace="team-a", key="own", value="mine"))
    foreign = store.write(MemoryEntryCreate(namespace="team_a", key="secret", value="theirs"))
    hits = [{"memory_id": foreign.id, "distance": 0.1}, {"memory_id": own.id, "distance": 0.2}]
    monkeypatch.setattr(engine.vector_store, "search", lambda *a, **k: hits)
    results = engine.search_semantic("anything", "team-a")
    assert [e.id for e in results] == [own.id]
