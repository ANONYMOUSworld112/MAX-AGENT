import pytest
from core.verification import (
    VerificationEngine,
    VerificationOutcome,
    VerificationReport,
    WindowVerifier,
    ProcessVerifier,
    ElementVerifier,
    TextVerifier,
    URLVerifier,
    FileVerifier,
    StateDiffVerifier,
)
from core.perception.state_builder import ComputerState


def test_verification_engine_aggregation():
    engine = VerificationEngine()

    rep_ok1 = VerificationReport(outcome=VerificationOutcome.SUCCESS)
    rep_ok2 = VerificationReport(outcome=VerificationOutcome.SUCCESS)
    agg_ok = engine.evaluate([rep_ok1, rep_ok2])
    assert agg_ok.outcome == VerificationOutcome.SUCCESS
    assert agg_ok.is_verified is True

    rep_fail = VerificationReport(outcome=VerificationOutcome.FAILURE, errors=["Element missing"])
    agg_fail = engine.evaluate([rep_ok1, rep_fail])
    assert agg_fail.outcome == VerificationOutcome.FAILURE
    assert agg_fail.is_verified is False
    assert len(agg_fail.errors) == 1

    rep_unk = VerificationReport(outcome=VerificationOutcome.UNKNOWN)
    agg_unk = engine.evaluate([rep_ok1, rep_unk])
    assert agg_unk.outcome == VerificationOutcome.UNKNOWN


def test_process_verifier():
    pv = ProcessVerifier()
    # Check Python process itself
    rep_proc = pv.verify_process_running("python")
    assert rep_proc.outcome == VerificationOutcome.SUCCESS

    # Exit code
    rep_ec0 = pv.verify_exit_code(0, expected_code=0)
    assert rep_ec0.outcome == VerificationOutcome.SUCCESS

    rep_ec1 = pv.verify_exit_code(1, expected_code=0)
    assert rep_ec1.outcome == VerificationOutcome.FAILURE


def test_element_verifier():
    ev = ElementVerifier()
    element = {"name": "SubmitButton", "is_enabled": True, "text": "Save & Continue"}

    rep_ok = ev.verify_element_state(element, expected_enabled=True, expected_text="Save")
    assert rep_ok.outcome == VerificationOutcome.SUCCESS

    rep_fail = ev.verify_element_state(element, expected_enabled=False)
    assert rep_fail.outcome == VerificationOutcome.FAILURE


def test_text_verifier():
    tv = TextVerifier()
    content = "The quick brown fox jumps over the lazy dog"

    rep_sub = tv.verify_contains(content, "brown fox")
    assert rep_sub.outcome == VerificationOutcome.SUCCESS

    rep_all = tv.verify_all_present(content, ["quick", "fox", "lazy"])
    assert rep_all.outcome == VerificationOutcome.SUCCESS

    rep_miss = tv.verify_all_present(content, ["quick", "elephant"])
    assert rep_miss.outcome == VerificationOutcome.FAILURE


def test_url_verifier():
    uv = URLVerifier()
    url = "https://github.com/google/gemini/issues/42"

    rep_dom = uv.verify_url_domain(url, "github.com")
    assert rep_dom.outcome == VerificationOutcome.SUCCESS

    rep_path = uv.verify_path_contains(url, "/issues/")
    assert rep_path.outcome == VerificationOutcome.SUCCESS

    rep_bad = uv.verify_url_domain(url, "example.com")
    assert rep_bad.outcome == VerificationOutcome.FAILURE


def test_file_verifier(tmp_path):
    fv = FileVerifier()
    test_f = tmp_path / "sample.txt"
    test_f.write_text("MAX OS Verification Test\nDeterministic verification.", encoding="utf-8")

    rep_ex = fv.verify_files_exist([str(test_f)])
    assert rep_ex.outcome == VerificationOutcome.SUCCESS

    rep_cnt = fv.verify_file_content(str(test_f), "Deterministic verification")
    assert rep_cnt.outcome == VerificationOutcome.SUCCESS

    sha = fv.compute_sha256(str(test_f))
    assert sha is not None
    assert len(sha) == 64


def test_state_diff_verifier():
    sdv = StateDiffVerifier()

    s_before = ComputerState(
        active_window="Terminal",
        visible_windows=[],
        processes=[],
        monitors=[],
        cursor_pos=(100, 100),
    )
    s_after = ComputerState(
        active_window="VS Code",
        visible_windows=[],
        processes=[],
        monitors=[],
        cursor_pos=(250, 400),
    )

    rep_diff = sdv.verify_state_transition(
        s_before,
        s_after,
        expected_window_change=True,
        expected_cursor_moved=True,
    )
    assert rep_diff.outcome == VerificationOutcome.SUCCESS
