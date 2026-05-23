import json
import sqlite3
from datetime import datetime

from common.config import settings
from common.schema import AgentResponse, EvalScore, RouteDecision, Signal, TriageCluster

DB_FILE = "agentlab.db"

def get_sqlite_conn():
    conn = sqlite3.connect(DB_FILE)
    # Ensure tables exist
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_responses (
            request_id TEXT,
            agent_id TEXT,
            output TEXT,
            success INTEGER,
            tokens_in INTEGER,
            tokens_out INTEGER,
            latency_ms REAL,
            tool_calls TEXT,
            self_reports TEXT,
            timestamp TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            request_id TEXT,
            agent_id TEXT,
            timestamp TEXT,
            kind TEXT,
            value REAL,
            source TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eval_scores (
            agent_id TEXT,
            task_family TEXT,
            pass_k REAL,
            n_trials INTEGER,
            ci_low REAL,
            ci_high REAL,
            timestamp TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS route_decisions (
            request_id TEXT,
            chosen_agent_id TEXT,
            router_kind TEXT,
            score REAL,
            explanation TEXT,
            candidates TEXT,
            decision_latency_ms REAL,
            timestamp TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS triage_clusters (
            cluster_id TEXT,
            size INTEGER,
            cause_step TEXT,
            cause_agent_id TEXT,
            symptom_steps TEXT,
            localization_basis TEXT,
            root_cause TEXT,
            proposed_tasks TEXT,
            status TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    return conn

# Mockable Storage Abstraction
def write_agent_response(resp: AgentResponse, success: bool | None = None) -> None:
    timestamp = datetime.utcnow().isoformat()
    if settings.mock:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO agent_responses
            (request_id, agent_id, output, success, tokens_in, tokens_out,
             latency_ms, tool_calls, self_reports, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resp.request_id,
                resp.agent_id,
                resp.output,
                1 if success else (0 if success is False else None),
                resp.tokens_in,
                resp.tokens_out,
                resp.latency_ms,
                json.dumps(resp.tool_calls),
                json.dumps(resp.self_reports),
                timestamp
            )
        )
        conn.commit()
        conn.close()
    else:
        # Real GCP BigQuery write
        from google.cloud import bigquery
        client = bigquery.Client(project=settings.gcp.project_id)
        table_id = f"{settings.gcp.project_id}.{settings.gcp.dataset_signals}.agent_responses"
        row = {
            "request_id": resp.request_id,
            "agent_id": resp.agent_id,
            "output": resp.output,
            "success": success,
            "tokens_in": resp.tokens_in,
            "tokens_out": resp.tokens_out,
            "latency_ms": resp.latency_ms,
            "tool_calls": json.dumps(resp.tool_calls),
            "self_reports": json.dumps(resp.self_reports),
            "timestamp": timestamp
        }
        client.insert_rows_json(table_id, [row])

def write_signal(sig: Signal) -> None:
    timestamp_str = sig.timestamp.isoformat()
    if settings.mock:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO signals (request_id, agent_id, timestamp, kind, value, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (sig.request_id, sig.agent_id, timestamp_str, sig.kind, sig.value, sig.source)
        )
        conn.commit()
        conn.close()
    else:
        from google.cloud import bigquery
        client = bigquery.Client(project=settings.gcp.project_id)
        table_id = f"{settings.gcp.project_id}.{settings.gcp.dataset_signals}.signals"
        row = {
            "request_id": sig.request_id,
            "agent_id": sig.agent_id,
            "timestamp": timestamp_str,
            "kind": sig.kind,
            "value": sig.value,
            "source": sig.source
        }
        client.insert_rows_json(table_id, [row])

def write_eval_score(score: EvalScore) -> None:
    timestamp_str = score.timestamp.isoformat()
    if settings.mock:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO eval_scores
            (agent_id, task_family, pass_k, n_trials, ci_low, ci_high, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                score.agent_id,
                score.task_family.value,
                score.pass_k,
                score.n_trials,
                score.ci_low,
                score.ci_high,
                timestamp_str
            )
        )
        conn.commit()
        conn.close()
    else:
        from google.cloud import bigquery
        client = bigquery.Client(project=settings.gcp.project_id)
        table_id = f"{settings.gcp.project_id}.{settings.gcp.dataset_evals}.eval_scores"
        row = {
            "agent_id": score.agent_id,
            "task_family": score.task_family.value,
            "pass_k": score.pass_k,
            "n_trials": score.n_trials,
            "ci_low": score.ci_low,
            "ci_high": score.ci_high,
            "timestamp": timestamp_str
        }
        client.insert_rows_json(table_id, [row])

def write_route_decision(dec: RouteDecision) -> None:
    timestamp = datetime.utcnow().isoformat()
    if settings.mock:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO route_decisions
            (request_id, chosen_agent_id, router_kind, score, explanation, candidates,
             decision_latency_ms, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dec.request_id,
                dec.chosen_agent_id,
                dec.router_kind,
                dec.score,
                dec.explanation,
                json.dumps(dec.candidates),
                dec.decision_latency_ms,
                timestamp
            )
        )
        conn.commit()
        conn.close()
    else:
        from google.cloud import bigquery
        client = bigquery.Client(project=settings.gcp.project_id)
        table_id = f"{settings.gcp.project_id}.{settings.gcp.dataset_signals}.route_decisions"
        row = {
            "request_id": dec.request_id,
            "chosen_agent_id": dec.chosen_agent_id,
            "router_kind": dec.router_kind,
            "score": dec.score,
            "explanation": dec.explanation,
            "candidates": json.dumps(dec.candidates),
            "decision_latency_ms": dec.decision_latency_ms,
            "timestamp": timestamp
        }
        client.insert_rows_json(table_id, [row])

def write_triage_cluster(cluster: TriageCluster) -> None:
    timestamp = datetime.utcnow().isoformat()
    if settings.mock:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO triage_clusters
            (cluster_id, size, cause_step, cause_agent_id, symptom_steps,
             localization_basis, root_cause, proposed_tasks, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cluster.cluster_id,
                cluster.size,
                cluster.cause_step.value,
                cluster.cause_agent_id,
                json.dumps([s.value for s in cluster.symptom_steps]),
                cluster.localization_basis,
                cluster.root_cause,
                json.dumps(cluster.proposed_tasks),
                cluster.status,
                timestamp
            )
        )
        conn.commit()
        conn.close()
    else:
        from google.cloud import bigquery
        client = bigquery.Client(project=settings.gcp.project_id)
        table_id = f"{settings.gcp.project_id}.{settings.gcp.dataset_signals}.triage_clusters"
        row = {
            "cluster_id": cluster.cluster_id,
            "size": cluster.size,
            "cause_step": cluster.cause_step.value,
            "cause_agent_id": cluster.cause_agent_id,
            "symptom_steps": json.dumps([s.value for s in cluster.symptom_steps]),
            "localization_basis": cluster.localization_basis,
            "root_cause": cluster.root_cause,
            "proposed_tasks": json.dumps(cluster.proposed_tasks),
            "status": cluster.status,
            "timestamp": timestamp
        }
        client.insert_rows_json(table_id, [row])

def query_signals(since: datetime) -> list[Signal]:
    since_str = since.isoformat()
    signals_list = []
    if settings.mock:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT request_id, agent_id, timestamp, kind, value, source "
            "FROM signals WHERE timestamp >= ?",
            (since_str,)
        )
        rows = cursor.fetchall()
        for r in rows:
            signals_list.append(Signal(
                request_id=r[0],
                agent_id=r[1],
                timestamp=datetime.fromisoformat(r[2]),
                kind=r[3],
                value=r[4],
                source=r[5]
            ))
        conn.close()
    else:
        from google.cloud import bigquery
        client = bigquery.Client(project=settings.gcp.project_id)
        query = f"""
            SELECT request_id, agent_id, timestamp, kind, value, source
            FROM `{settings.gcp.project_id}.{settings.gcp.dataset_signals}.signals`
            WHERE timestamp >= @since
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("since", "STRING", since_str)
            ]
        )
        query_job = client.query(query, job_config=job_config)
        for r in query_job:
            signals_list.append(Signal(
                request_id=r["request_id"],
                agent_id=r["agent_id"],
                timestamp=datetime.fromisoformat(r["timestamp"]),
                kind=r["kind"],
                value=r["value"],
                source=r["source"]
            ))
    return signals_list

def query_eval_scores(since: datetime) -> list[EvalScore]:
    since_str = since.isoformat()
    scores_list = []
    if settings.mock:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT agent_id, task_family, pass_k, n_trials, ci_low, "
            "ci_high, timestamp FROM eval_scores WHERE timestamp >= ?",
            (since_str,)
        )
        rows = cursor.fetchall()
        for r in rows:
            scores_list.append(EvalScore(
                agent_id=r[0],
                task_family=r[1],
                pass_k=r[2],
                n_trials=r[3],
                ci_low=r[4],
                ci_high=r[5],
                timestamp=datetime.fromisoformat(r[6])
            ))
        conn.close()
    else:
        from google.cloud import bigquery
        client = bigquery.Client(project=settings.gcp.project_id)
        query = f"""
            SELECT agent_id, task_family, pass_k, n_trials, ci_low, ci_high, timestamp
            FROM `{settings.gcp.project_id}.{settings.gcp.dataset_evals}.eval_scores`
            WHERE timestamp >= @since
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("since", "STRING", since_str)
            ]
        )
        query_job = client.query(query, job_config=job_config)
        for r in query_job:
            scores_list.append(EvalScore(
                agent_id=r["agent_id"],
                task_family=r["task_family"],
                pass_k=r["pass_k"],
                n_trials=r["n_trials"],
                ci_low=r["ci_low"],
                ci_high=r["ci_high"],
                timestamp=datetime.fromisoformat(r["timestamp"])
            ))
    return scores_list
