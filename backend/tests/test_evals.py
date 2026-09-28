from replypilot.evals import run_local_eval


def test_local_quality_gate() -> None:
    result = run_local_eval()
    assert result["triage_accuracy"] == 1.0
    assert result["mean_draft_score"] >= 4.0
    assert result["draft_threshold_passed"] is True
