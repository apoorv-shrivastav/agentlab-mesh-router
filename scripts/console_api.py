import sys
import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from common.bq import DB_FILE, get_sqlite_conn
from triage.runner import approve_triage_tasks, reject_triage_tasks, run_triage_job

def get_data():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. Fetch latest signals (limit 150)
    cursor.execute("SELECT request_id, agent_id, timestamp, kind, value, source FROM signals ORDER BY timestamp DESC LIMIT 150")
    signals = [{"request_id": r[0], "agent_id": r[1], "timestamp": r[2], "kind": r[3], "value": r[4], "source": r[5]} for r in cursor.fetchall()]
    
    # 2. Fetch eval scores
    cursor.execute("SELECT agent_id, task_family, pass_k, n_trials, ci_low, ci_high, timestamp FROM eval_scores ORDER BY timestamp ASC")
    eval_scores = [{"agent_id": r[0], "task_family": r[1], "pass_k": r[2], "n_trials": r[3], "ci_low": r[4], "ci_high": r[5], "timestamp": r[6]} for r in cursor.fetchall()]
    
    # 3. Fetch latest route decisions (limit 50)
    cursor.execute("SELECT request_id, chosen_agent_id, router_kind, score, explanation, candidates, decision_latency_ms, timestamp FROM route_decisions ORDER BY timestamp DESC LIMIT 50")
    route_decisions = []
    for r in cursor.fetchall():
        try:
            candidates = json.loads(r[5])
        except Exception:
            candidates = r[5]
        route_decisions.append({
            "request_id": r[0],
            "chosen_agent_id": r[1],
            "router_kind": r[2],
            "score": r[3],
            "explanation": r[4],
            "candidates": candidates,
            "decision_latency_ms": r[6],
            "timestamp": r[7]
        })
        
    # 4. Fetch triage clusters
    cursor.execute("SELECT cluster_id, size, cause_step, cause_agent_id, symptom_steps, localization_basis, root_cause, proposed_tasks, status, timestamp FROM triage_clusters ORDER BY timestamp DESC")
    triage_clusters = []
    for r in cursor.fetchall():
        try:
            symptoms = json.loads(r[4])
        except Exception:
            symptoms = r[4]
        try:
            tasks = json.loads(r[7])
        except Exception:
            tasks = r[7]
        triage_clusters.append({
            "cluster_id": r[0],
            "size": r[1],
            "cause_step": r[2],
            "cause_agent_id": r[3],
            "symptom_steps": symptoms,
            "localization_basis": r[5],
            "root_cause": r[6],
            "proposed_tasks": tasks,
            "status": r[8],
            "timestamp": r[9]
        })
        
    conn.close()
    
    print(json.dumps({
        "signals": signals,
        "eval_scores": eval_scores,
        "route_decisions": route_decisions,
        "triage_clusters": triage_clusters
    }, indent=2))

def approve(cluster_id):
    success = approve_triage_tasks(cluster_id, DB_FILE)
    print(json.dumps({"success": success}))

def reject(cluster_id):
    success = reject_triage_tasks(cluster_id, DB_FILE)
    print(json.dumps({"success": success}))

def trigger_failure():
    # Insert new signals and bad runs to simulate active failure
    conn = get_sqlite_conn()
    cursor = conn.cursor()
    
    # We clear out older triage clusters to make sure our new failure is the active one
    cursor.execute("DELETE FROM triage_clusters")
    
    req_id = f"fail-{uuid.uuid4().hex[:6]}"
    now_str = datetime.utcnow().isoformat()
    
    # Insert a bad agent response for causal-estimation
    cursor.execute(
        """
        INSERT INTO agent_responses
        (request_id, agent_id, output, success, tokens_in, tokens_out,
         latency_ms, tool_calls, self_reports, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            req_id,
            "causal-estimation",
            "Causal Estimation Complete.\nLift: +48.5%\n[extreme variance warning]",
            0,
            300,
            400,
            450.0,
            "[]",
            json.dumps(["Extreme variance detected during covariate adjustment."]),
            now_str,
        )
    )
    # Insert out_of_bounds signal
    cursor.execute("INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?)", (req_id, "causal-estimation", now_str, "out_of_bounds", 1.0, "explicit"))
    cursor.execute("INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?)", (req_id, "causal-estimation", now_str, "self_report", 1.0, "self_report"))
    
    # Readout symptom response
    cursor.execute(
        """
        INSERT INTO agent_responses
        (request_id, agent_id, output, success, tokens_in, tokens_out,
         latency_ms, tool_calls, self_reports, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            req_id,
            "readout",
            "MEMO recommendation: SHIP (+48.5% lift)",
            0,
            400,
            300,
            150.0,
            "[]",
            json.dumps(["Drafting memo with contaminated lift input."]),
            now_str,
        )
    )
    cursor.execute("INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?)", (req_id, "readout", now_str, "low_confidence_output", 1.0, "classifier"))
    
    # Also adjust the latest eval score for causal-estimation to be very low
    cursor.execute(
        """
        INSERT INTO eval_scores
        (agent_id, task_family, pass_k, n_trials, ci_low, ci_high, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("causal-estimation", "causal_estimation", 0.18, 100, 0.13, 0.23, now_str)
    )
    # Readout score drops as well
    cursor.execute(
        """
        INSERT INTO eval_scores
        (agent_id, task_family, pass_k, n_trials, ci_low, ci_high, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("readout", "readout", 0.38, 100, 0.32, 0.44, now_str)
    )
    
    conn.commit()
    conn.close()
    
    # Run triage job immediately to create the cluster
    triage_clusters = run_triage_job(DB_FILE)
    print(json.dumps({"status": "failure_triggered", "clusters_created": len(triage_clusters)}))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No command provided"}))
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "get_data":
        get_data()
    elif cmd == "approve":
        approve(sys.argv[2])
    elif cmd == "reject":
        reject(sys.argv[2])
    elif cmd == "trigger_failure":
        trigger_failure()
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))
