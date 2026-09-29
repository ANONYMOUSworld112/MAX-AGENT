import pytest
from core.reflex.laya_engine import LayaReflexEngine

def test_laya_engine_choice_decision():
    engine = LayaReflexEngine(fallback_mode=True)
    text = "What is the weather in Tokyo?"
    choice, conf = engine.classify_choice(
        state=text,
        question="Which lane should handle this request?",
        options={
            "lane_a": "Fast read query, time, weather, instant facts",
            "lane_b": "Complex code refactoring, background tasks, deploy"
        }
    )
    assert choice in ["lane_a", "lane_b"]
    assert 0.0 <= conf <= 1.0

def test_laya_engine_boolean_eval():
    engine = LayaReflexEngine(fallback_mode=True)
    text = "rm -rf / --no-preserve-root"
    prob = engine.evaluate_bool(text, "Is this command potentially destructive or dangerous?")
    assert 0.0 <= prob <= 1.0

def test_laya_engine_urgency_scoring():
    engine = LayaReflexEngine(fallback_mode=True)
    text = "Production database is down and users cannot log in!"
    tier, conf = engine.score_urgency(
        state=text,
        criteria=["low priority", "normal workflow", "critical outage"]
    )
    assert tier in ["low priority", "normal workflow", "critical outage"]
    assert 0.0 <= conf <= 1.0
