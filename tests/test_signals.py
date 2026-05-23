import pytest
from datetime import datetime
from common.schema import Signal
from signals.regex.patterns import extract_regex_signals
from signals.explicit.collectors import collect_explicit_signals
from signals.classifiers.infer import infer_signals
from sentry.online_cusum import detect_drift_in_series, CUSUMDetector, EWMADetector
from sentry.offline_regression import mcnemar_test, bootstrap_difference_ci, benjamini_hochberg

def test_regex_signal_extraction():
    req_id = "test-req-regex"
    agent_id = "test-agent"
    
    # 1. Matches refusal pattern
    refusal_output = "I'm sorry, but as an AI language model I cannot answer this request."
    sigs = extract_regex_signals(req_id, agent_id, refusal_output)
    kinds = [s.kind for s in sigs]
    assert "refusal" in kinds
    assert len(sigs) == 1
    
    # 2. Matches task failure
    failure_output = "An unexpected exception occurred: failed to parse inputs."
    sigs = extract_regex_signals(req_id, agent_id, failure_output)
    kinds = [s.kind for s in sigs]
    assert "task_failure" in kinds
    
    # 3. Clean output
    clean_output = "ATE estimate: +2.4%, p-value: 0.0031. SRM check passed successfully."
    sigs = extract_regex_signals(req_id, agent_id, clean_output)
    assert len(sigs) == 0

def test_explicit_signal_collection():
    req_id = "test-req-explicit"
    agent_id = "test-agent"
    
    # 1. Normal run
    sigs = collect_explicit_signals(
        request_id=req_id,
        agent_id=agent_id,
        latency_ms=150.0,
        tokens_in=200,
        tokens_out=300,
        cost_per_1k=0.01,
        tool_calls=[]
    )
    
    kinds = {s.kind: s.value for s in sigs}
    assert "latency" in kinds
    assert kinds["latency"] == 150.0
    assert "cost" in kinds
    assert kinds["cost"] == (500 * (0.01 / 1000.0))
    assert "tool_error" not in kinds
    
    # 2. Tool error and handoff failure
    sigs = collect_explicit_signals(
        request_id=req_id,
        agent_id=agent_id,
        latency_ms=250.0,
        tokens_in=100,
        tokens_out=100,
        cost_per_1k=0.01,
        tool_calls=[{"name": "test_tool", "status": "error"}],
        handoff_failed=True
    )
    
    kinds = {s.kind: s.value for s in sigs}
    assert "tool_error" in kinds
    assert kinds["tool_error"] == 1.0
    assert "malformed_handoff" in kinds
    assert kinds["malformed_handoff"] == 1.0

def test_classifier_inferences():
    req_id = "test-req-class"
    agent_id = "test-agent"
    
    # Check that heuristic fallbacks are triggered correctly and map categories
    # Refusal text
    output_refusal = "Sorry, I am unable to process this request because it violates rules."
    sigs = infer_signals(req_id, agent_id, output_refusal)
    assert any(s.kind == "refusal" for s in sigs)
    
    # Low confidence text
    output_low_conf = "The output variance is high, point estimate is extreme and out of bounds."
    sigs = infer_signals(req_id, agent_id, output_low_conf)
    assert any(s.kind == "low_confidence_output" for s in sigs)

def test_online_cusum_drift_detection():
    # Target mean = 0.05, target std = 0.02
    # Baseline stable sequence
    stable_seq = [0.05 + float(i % 3 - 1) * 0.01 for i in range(20)]
    
    # Injected drift starting at index 20
    drift_seq = stable_seq + [0.15, 0.16, 0.17, 0.18, 0.20, 0.22]
    
    # Run CUSUM
    drift_detected, index = detect_drift_in_series(drift_seq, baseline_mean=0.05, baseline_std=0.02, method="cusum")
    assert drift_detected
    assert index >= 20 # Breach occurred in the drift period
    
    # Test on stable sequence (should not detect drift)
    no_drift, _ = detect_drift_in_series(stable_seq, baseline_mean=0.05, baseline_std=0.02, method="cusum")
    assert not no_drift

def test_online_ewma_drift_detection():
    stable_seq = [0.1 for _ in range(15)]
    drift_seq = stable_seq + [0.5, 0.6, 0.7, 0.8]
    
    drift_detected, index = detect_drift_in_series(drift_seq, baseline_mean=0.1, baseline_std=0.05, method="ewma", lambda_val=0.2, L_factor=3.0)
    assert drift_detected
    assert index >= 15

def test_mcnemar_regression_detection():
    # 1. Injected regression (baseline has 95% success, comparison has 40% success)
    base_outcomes = [1] * 38 + [0] * 2  # 38/40 success
    comp_outcomes = [1] * 16 + [0] * 24 # 16/40 success
    
    p_val = mcnemar_test(base_outcomes, comp_outcomes)
    mean_diff, ci_low, ci_high = bootstrap_difference_ci(base_outcomes, comp_outcomes)
    
    assert p_val < 0.01 # Highly significant regression
    assert mean_diff < -0.4 # Significant drop in performance
    assert ci_high < 0.0 # CI does not span 0
    
    # 2. Random noise (both have roughly same success, should not trigger)
    base_noise = [1] * 35 + [0] * 5
    comp_noise = [1] * 34 + [0] * 6
    
    p_val_noise = mcnemar_test(base_noise, comp_noise)
    assert p_val_noise > 0.5 # Not significant

def test_benjamini_hochberg_correction():
    # Hypotheses with p-values
    p_values = {
        "family_A": 0.0001,  # Significant
        "family_B": 0.005,   # Significant
        "family_C": 0.35     # Non-significant
    }
    
    rejections = benjamini_hochberg(p_values, alpha_fdr=0.05)
    assert rejections["family_A"] is True
    assert rejections["family_B"] is True
    assert rejections["family_C"] is False
