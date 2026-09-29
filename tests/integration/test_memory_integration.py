import pytest
from core.memory.context_heap import MemoryContextHeap
from core.memory.token_budget import TokenBudgetCompressor
from memory.memory_manager import format_memory_for_prompt, update_memory, load_memory


def test_memory_context_heap_and_token_budget_pipeline():
    heap = MemoryContextHeap()

    # Load from system config / memory
    heap.set_identity("CyberBlack AI-agent MAX - Autonomous deterministic AI OS")
    heap.set_preference("theme", "cyberpunk_dark")
    heap.set_behavioral_pattern("verbosity", "concise, direct execution")
    heap.set_project_state("phase", "Phase 15 integration")

    # Add conversation history
    for i in range(20):
        heap.add_conversation_turn("user", f"Instruction query number {i}")
        heap.add_conversation_turn("assistant", f"Acknowledged task {i}, executing via agent swarm.")

    # Compress with tight budget
    composite = heap.get_composite_context(max_tokens=500)
    compressor = TokenBudgetCompressor(max_budget=200)
    compressed_prompt = compressor.compress(composite)

    assert "CyberBlack AI-agent MAX" in compressed_prompt
    assert len(compressed_prompt.split()) <= 220
