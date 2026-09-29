import pytest
from core.memory.context_heap import MemoryContextHeap
from core.memory.token_budget import TokenBudgetCompressor

def test_memory_context_heap_layers():
    heap = MemoryContextHeap()
    heap.set_identity("You are MAX. Absolute loyalty to user.")
    heap.set_preference("editor", "VS Code")
    heap.set_behavioral_pattern("avoid_eval", "Never use eval() in python scripts")
    heap.set_project_state("active_branch", "feat/max-integration")
    heap.add_conversation_turn("user", "Hello MAX")
    heap.add_conversation_turn("assistant", "Greetings sir, all systems nominal.")

    ctx = heap.get_composite_context(max_tokens=2048)
    assert "MAX" in ctx
    assert "VS Code" in ctx
    assert "avoid_eval" in ctx
    assert "feat/max-integration" in ctx
    assert "Greetings sir" in ctx

def test_token_budget_compression():
    compressor = TokenBudgetCompressor(max_budget=50) # low budget
    huge_text = "word " * 200
    compressed = compressor.compress(huge_text)
    # Compressed must be significantly shorter
    assert len(compressed.split()) <= 55

