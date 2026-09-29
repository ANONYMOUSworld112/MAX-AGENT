import pytest
from PIL import Image
from core.perception import (
    ScreenCapture,
    MonitorInfo,
    AccessibilityEngine,
    UIElement,
    BrowserDOMExtractor,
    TextDetector,
    ElementDetector,
    UIDetector,
    StateBuilder,
    ComputerState,
)
from core.max_infra.kill_switch import KillSwitch, KillSwitchTrippedError


def test_screen_capture_coordinates():
    sc = ScreenCapture()
    monitors = sc.get_monitors()
    assert len(monitors) >= 1
    mon = monitors[0]

    # Test coordinate normalization
    nx, ny = sc.normalize_coordinates(mon.width // 2, mon.height // 2, monitor=mon)
    assert 0.4 <= nx <= 0.6
    assert 0.4 <= ny <= 0.6

    px, py = sc.denormalize_coordinates(0.5, 0.5, monitor=mon)
    assert abs(px - (mon.left + mon.width // 2)) <= 2
    assert abs(py - (mon.top + mon.height // 2)) <= 2


def test_ui_element_properties():
    el = UIElement(
        name="SubmitButton",
        control_type="Button",
        bounding_rect=(100, 200, 300, 250),
    )
    assert el.center_point == (200, 225)
    assert el.is_enabled is True


def test_browser_dom_extraction():
    dom = BrowserDOMExtractor()
    nodes = dom.extract_dom_snapshot()
    assert len(nodes) >= 2
    assert any(n.tag == "button" for n in nodes)


def test_text_detector_graceful_fallback():
    td = TextDetector()
    test_img = Image.new("RGB", (100, 100), color="white")
    results = td.detect_text(test_img)
    assert isinstance(results, list)


def test_ui_detector_fallback_hierarchy():
    ui_det = UIDetector()
    test_img = Image.new("RGB", (300, 300), color="blue")

    # Matching browser DOM element
    res_dom = ui_det.find_target("submit-btn", screenshot=test_img)
    assert res_dom.success is True
    assert res_dom.level == 3

    # Non-existent element falling back through hierarchy to Level 7
    res_fallback = ui_det.find_target("completely_nonexistent_xyz", screenshot=test_img)
    assert res_fallback.level == 7
    assert res_fallback.success is False
    assert "Levels 1-6 failed" in res_fallback.reason


def test_state_builder():
    sb = StateBuilder()
    state = sb.build_state()
    assert isinstance(state, ComputerState)
    assert state.active_window != ""
    assert isinstance(state.visible_windows, list)
    assert isinstance(state.monitors, list)
    assert len(state.cursor_pos) == 2


def test_perception_kill_switch_guard():
    ks = KillSwitch.get_instance()
    try:
        ks.trip("Emergency test shutdown")
        sc = ScreenCapture()
        with pytest.raises(KillSwitchTrippedError):
            sc.capture_screen()
    finally:
        ks.reset()
