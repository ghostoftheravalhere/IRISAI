"""Unit tests for Semantic Memory & Personal Knowledge System."""

from __future__ import annotations

from backend.memory.embedding_service import LocalEmbeddingProvider
from backend.memory.knowledge_graph import KnowledgeGraphStore
from backend.memory.memory_manager import MemoryManager
from backend.memory.memory_models import EntityRelation, MemoryItem, MemoryLayer
from backend.memory.memory_privacy import MemoryPrivacyFilter
from backend.memory.vector_store import LocalVectorStore, cosine_similarity


def test_embedding_provider_and_cosine_similarity():
    provider = LocalEmbeddingProvider()
    v1 = provider.generate_embedding("Open Chrome browser search ChatGPT")
    v2 = provider.generate_embedding("Open Chrome search OpenAI ChatGPT")
    v3 = provider.generate_embedding("Unrelated recipes for dinner")

    sim_close = cosine_similarity(v1, v2)
    sim_far = cosine_similarity(v1, v3)

    assert len(v1) == 384
    assert sim_close > sim_far


def test_memory_privacy_filter_sanitization():
    privacy = MemoryPrivacyFilter()
    raw = "My card number is 4111 2222 3333 4444 and secret password is password: mysecretpass"
    sanitized = privacy.sanitize_content(raw)

    assert "[REDACTED CARD]" in sanitized
    assert "[REDACTED SECRET]" in sanitized
    assert privacy.should_forget("User prefers Dark Theme in Chrome", "Dark Theme") is True


def test_memory_manager_remember_and_recall():
    manager = MemoryManager()
    manager.remember("User prefers Chrome browser for daily tasks", MemoryLayer.PREFERENCE, tags=["browser"])
    manager.remember("Project IRIS AI V3 baseline setup complete", MemoryLayer.WORKSPACE, tags=["project"])

    results = manager.recall("What is the preferred browser?")
    assert len(results) > 0
    assert "Chrome" in results[0].memory_item.content


def test_knowledge_graph_and_forget():
    manager = MemoryManager()
    rel = manager.add_knowledge_relation("User", "PREFERS", "Chrome")
    assert rel.subject == "User"

    manager.remember("User goal is to build AI agents in Python", MemoryLayer.SEMANTIC)
    forgot = manager.forget_topic("AI agents")
    assert forgot >= 1
