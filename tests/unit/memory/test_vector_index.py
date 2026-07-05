"""Tests for emergence.memory.vector_index — M15."""

from __future__ import annotations

from emergence.memory.vector_index import VectorIndex


class TestVectorIndex:
    def test_search_returns_relevant_documents(self):
        index = VectorIndex()
        index.add("a", "event-driven process architecture with mailboxes")
        index.add("b", "database indexing and query optimization")
        index.add("c", "capability-based security for kernel services")

        results = index.search("process mailbox security", top_k=2)
        assert len(results) >= 1
        assert results[0].score > 0

    def test_search_empty_index(self):
        index = VectorIndex()
        assert index.search("anything") == []

    def test_remove_document(self):
        index = VectorIndex()
        index.add("a", "hello world")
        index.remove("a")
        assert index.search("hello") == []
