import os
import uuid
import yaml
import sqlite3
import json
from datetime import datetime
from common.schema import TriageCluster, TaskFamily
from common.bq import write_triage_cluster
from triage.cluster import cluster_failed_requests
from triage.localize import localize_failure_cluster
from triage.generate_tasks import generate_triage_tasks
from triage.a2ui_surface import post_triage_alert

def run_triage_job(db_file: str = "agentlab.db") -> list[TriageCluster]:
    """
    Runs the automated fault localization and triage pipeline.
    Identifies failure clusters, attributes the cause step, generates new test tasks,
    writes them to DB, and posts Slack alert cards.
    """
    clusters_map = cluster_failed_requests(db_file)
    triage_clusters = []
    
    for label, traces in clusters_map.items():
        if not traces:
            continue
            
        cluster_id = f"cluster-{label}-{uuid.uuid4().hex[:6]}"
        
        # 1. Step Fault Localization
        cause_info = localize_failure_cluster(traces, db_file)
        
        # 2. Task Generation using Gemini
        tasks_info = generate_triage_tasks(
            cause_step=cause_info["cause_step"],
            cluster_traces=traces,
            localization_basis=cause_info["localization_basis"]
        )
        
        # 3. Create TriageCluster model instance
        cluster = TriageCluster(
            cluster_id=cluster_id,
            size=len(traces),
            cause_step=cause_info["cause_step"],
            cause_agent_id=cause_info["cause_agent_id"],
            symptom_steps=cause_info["symptom_steps"],
            localization_basis=cause_info["localization_basis"],
            root_cause=tasks_info["root_cause"],
            proposed_tasks=tasks_info["proposed_tasks"],
            status="proposed"
        )
        
        # 4. Save to Database
        write_triage_cluster(cluster)
        
        # 5. Post to Slack interactive channel
        post_triage_alert(cluster)
        
        triage_clusters.append(cluster)
        
    return triage_clusters

def update_cluster_status(cluster_id: str, status: str, db_file: str = "agentlab.db") -> bool:
    """Updates the status of a triage cluster in the database."""
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE triage_clusters
        SET status = ?
        WHERE cluster_id = ?
    """, (status, cluster_id))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

def approve_triage_tasks(cluster_id: str, db_file: str = "agentlab.db") -> bool:
    """
    Approves the triage cluster, updates status in DB, and appends the proposed
    tasks to the corresponding task family YAML file in harness/tasks.
    """
    # 1. Fetch cluster proposed tasks from DB
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT cause_step, proposed_tasks
        FROM triage_clusters
        WHERE cluster_id = ?
    """, (cluster_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print(f"[Approve] Cluster {cluster_id} not found.")
        return False
        
    cause_step_val = row[0]
    proposed_tasks = json.loads(row[1])
    
    # 2. Append tasks to harness YAML file
    tasks_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "harness", "tasks"
    )
    yaml_file = os.path.join(tasks_dir, f"{cause_step_val}.yaml")
    
    if not os.path.exists(yaml_file):
        print(f"[Approve] YAML file not found: {yaml_file}")
        return False
        
    try:
        with open(yaml_file, "r") as f:
            existing_tasks = yaml.safe_load(f) or []
    except Exception as e:
        print(f"[Approve] Failed to read {yaml_file}: {e}")
        existing_tasks = []
        
    for task in proposed_tasks:
        # Create a unique ID and format matching golden set
        task_id = f"triage-{uuid.uuid4().hex[:8]}"
        new_task = {
            "id": task_id,
            "prompt": task["prompt"],
            "expected": task["expected"],
            "difficulty": "medium"
        }
        existing_tasks.append(new_task)
        
    try:
        with open(yaml_file, "w") as f:
            yaml.safe_dump(existing_tasks, f, sort_keys=False)
        print(f"[Approve] Appended {len(proposed_tasks)} new tasks to {yaml_file}")
    except Exception as e:
        print(f"[Approve] Failed to write back to {yaml_file}: {e}")
        return False
        
    # 3. Update status in database
    return update_cluster_status(cluster_id, "approved", db_file)

def reject_triage_tasks(cluster_id: str, db_file: str = "agentlab.db") -> bool:
    """Rejects the triage cluster and updates status in DB."""
    return update_cluster_status(cluster_id, "rejected", db_file)
