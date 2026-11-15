"""Without the embedding package (the lean demo image) semantic search must switch off quietly: one warning, no ERROR per call."""
import logging

import pytest


@pytest.fixture
def vs_no_embeddings(monkeypatch):
    import chromadb
    from chromadb.utils import embedding_functions
    import memory.vector_store as vs

    saved = (vs._client, vs._ef, vs._init_failed, getattr(vs, "_embeddings_missing", False), dict(vs._collections))
    vs._client = vs._ef = None
    vs._init_failed = False
    vs._embeddings_missing = False
    vs._collections.clear()

    class FakeClient:  # a reachable ChromaDB; only the embedding function is missing
        def heartbeat(self):
            return 1
        def get_or_create_collection(self, **kw):  # would be reached only by the old bug
            raise ValueError("You must provide an embedding function to compute embeddings.")

    def missing(*a, **k):
        raise ImportError("No module named 'sentence_transformers'")

    monkeypatch.setattr(chromadb, "PersistentClient", lambda path: FakeClient())
    monkeypatch.setattr(embedding_functions, "SentenceTransformerEmbeddingFunction", missing)
    yield vs
    vs._client, vs._ef, vs._init_failed, vs._embeddings_missing = saved[:4]  # (old code has no flag: harmless attribute)
    vs._collections.clear(); vs._collections.update(saved[4])


def test_init_reports_unavailable_every_time_not_just_the_first(vs_no_embeddings):
    vs = vs_no_embeddings
    assert vs._init() is False
    assert vs._init() is False, "the second call used to return True because the client was already set"
    assert vs._client is not None, "ChromaDB itself is up, so health checks still see it"
    assert vs._init_failed is True


def test_memory_calls_log_no_errors_and_return_nothing(vs_no_embeddings, caplog):
    vs = vs_no_embeddings
    with caplog.at_level(logging.WARNING, logger="claudeos.memory.vector"):
        for _ in range(3):
            assert vs.upsert("m1", "global", "some text", {"k": "v"}) is None
            assert vs.search("some text", "global") in ([], None) or not vs.search("some text", "global")
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors == [], [r.getMessage() for r in errors]
    # Only this module's own logger: the app's warmup thread (claudeos.api) logs a similar line of its own, and caplog sees both.
    warnings = [r for r in caplog.records if r.name == "claudeos.memory.vector" and "semantic search disabled" in r.getMessage()]
    assert len(warnings) == 1, "warn once, not on every call"
