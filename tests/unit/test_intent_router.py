import pytest
from core.reflex.intent_router import ReflexIntentRouter, LaneType

def test_intent_router_lane_a_fast_read():
    router = ReflexIntentRouter(fallback_mode=True)
    decision = router.route_input("What is the current time and battery percentage?")
    assert decision.lane == LaneType.LANE_A
    assert decision.is_modifying is False

def test_intent_router_lane_b_dev_task():
    router = ReflexIntentRouter(fallback_mode=True)
    decision = router.route_input("Refactor the login function in auth.py and run pytest")
    assert decision.lane == LaneType.LANE_B
    assert decision.is_modifying is True
    assert decision.target_agent == "PolyglotDeveloper"

def test_intent_router_lane_b_calendar():
    router = ReflexIntentRouter(fallback_mode=True)
    decision = router.route_input("Schedule a team sync meeting tomorrow at 2 PM")
    assert decision.lane == LaneType.LANE_B
    assert decision.target_agent == "CalendarAgent"
