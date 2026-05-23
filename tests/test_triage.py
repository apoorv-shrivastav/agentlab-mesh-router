import os
import shutil
import sqlite3
import json
import yaml
import pytest
from datetime import datetime
from common.schema import TaskFamily, TriageCluster
from triage.cluster import cluster_failed_requests
from triage.localize import localize_failure_cluster
from triage.runner import run_triage_job, approve_triage_tasks, reject_triage_tasks

DB_FILE = "agentlab.db"

@pytest.fixture(scope="module")
def setup_failed_traces():
    """Seeds a controlled failed trace cluster in the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Empty any existing test triage/responses first to keep it isolated
    cursor.execute("DELETE FROM agent_responses WHERE request_id LIKE 'test-triage-%'")
    cursor.execute("DELETE FROM signals WHERE request_id LIKE 'test-triage-%'")
    cursor.execute("DELETE FROM triage_clusters WHERE cluster_id LIKE 'cluster-%'")
    conn.commit()
    
    # We will seed 3 identical failed traces:
    # data-prep passes, causal-estimation degrades (produces out_of_bounds & self_report), readout propagates
    for i in range(3):
        req_id = f"test-triage-req-{i}"
        timestamp_str = datetime.utcnow().isoformat()
        
        # Step 1: Data Prep (Success)
        cursor.execute(
            "INSERT INTO agent_responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (req_id, "data-prep", "SRM check passed.", 1, 100, 100, 10.0, "[]", "[]", timestamp_str)
        )
        # Step 2: Causal Estimation (Degraded)
        cursor.execute(
            "INSERT INTO agent_responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (req_id, "causal-estimation", "ATE Point estimate: +48.5% (extreme variance)", 0, 100, 100, 10.0, "[]", json.dumps(["extreme variance"]), timestamp_str)
        )
        cursor.execute(
            "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?)",
            (req_id, "causal-estimation", timestamp_str, "out_of_bounds", 1.0, "explicit")
        )
        cursor.execute(
            "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?)",
            (req_id, "causal-estimation", timestamp_str, "self_report", 1.0, "self_report")
        )
        # Step 3: Readout (Propagated failure)
        cursor.execute(
            "INSERT INTO agent_responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (req_id, "readout", "MEMO: Recommendation to Ship.", 0, 100, 100, 10.0, "[]", "[]", timestamp_str)
        )
        cursor.execute(
            "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?)",
            (req_id, "readout", timestamp_str, "low_confidence_output", 1.0, "classifier")
        )
        
    conn.commit()
    conn.close()
    
    yield
    
    # Cleanup after tests
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM agent_responses WHERE request_id LIKE 'test-triage-%'")
    cursor.execute("DELETE FROM signals WHERE request_id LIKE 'test-triage-%'")
    cursor.execute("DELETE FROM triage_clusters WHERE cluster_id LIKE 'cluster-%'")
    conn.commit()
    conn.close()

def test_trace_clustering(setup_failed_traces):
    # Verify that the clustering gathers our test traces correctly
    clusters = cluster_failed_requests(DB_FILE)
    # Check that at least one cluster was identified
    assert len(clusters) > 0
    
    # Find our test cluster
    test_traces = []
    for lbl, traces in clusters.items():
        for t in traces:
            if t["request_id"].startswith("test-triage-req-"):
                test_traces.append(t)
                
    assert len(test_traces) == 3

def test_fault_localization(setup_failed_traces):
    clusters = cluster_failed_requests(DB_FILE)
    # Filter only our test traces
    test_traces = []
    for lbl, traces in clusters.items():
        for t in traces:
            if t["request_id"].startswith("test-triage-req-"):
                test_traces.append(t)
                
    # Run localization
    result = localize_failure_cluster(test_traces, DB_FILE)
    
    # Assert credit attribution is correctly localized to causal-estimation (Step 2)
    # and readout is identified as the downstream symptom step
    assert result["cause_step"] == TaskFamily.CAUSAL_ESTIMATION
    assert result["cause_agent_id"] == "causal-estimation"
    assert TaskFamily.READOUT in result["symptom_steps"]
    assert "oracle" in result["localization_basis"]

def test_triage_runner_and_approval(setup_failed_traces):
    # Backup the causal_estimation task YAML file to prevent permanent pollution
    tasks_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "harness", "tasks"
    )
    yaml_file = os.path.join(tasks_dir, "causal_estimation.yaml")
    backup_file = os.path.join(tasks_dir, "causal_estimation.yaml.bak")
    
    if os.path.exists(yaml_file):
        shutil.copyfile(yaml_file, backup_file)
        
    try:
        # 1. Run the full triage job pipeline
        triage_clusters = run_triage_job(DB_FILE)
        assert len(triage_clusters) > 0
        
        # Find the cluster that localized to causal_estimation
        test_cluster = None
        for c in triage_clusters:
            if c.cause_step == TaskFamily.CAUSAL_ESTIMATION:
                test_cluster = c
                break
                
        assert test_cluster is not None
        assert test_cluster.status == "proposed"
        
        # 2. Approve the triage tasks
        success = approve_triage_tasks(test_cluster.cluster_id, DB_FILE)
        assert success
        
        # Check status is updated to approved
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM triage_clusters WHERE cluster_id = ?", (test_cluster.cluster_id,))
        status = cursor.fetchone()[0]
        conn.close()
        assert status == "approved"
        
        # Check that YAML file contains the newly appended tasks
        with open(yaml_file, "r") as f:
            tasks = yaml.safe_load(f)
            
        task_prompts = [t["prompt"] for t in tasks]
        assert any("CUPED" in p or "causal" in p for p in task_prompts)
        
        # 3. Test Rejection
        reject_success = reject_triage_tasks(test_cluster.cluster_id, DB_FILE)
        assert reject_success
        
    finally:
        # Restore the backup file
        if os.path.exists(backup_file):
            shutil.move(backup_file, yaml_file)
