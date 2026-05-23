import sqlite3
from common.schema import TaskFamily

# Mapping agent IDs to TaskFamily
AGENT_TO_FAMILY = {
    "data-prep": TaskFamily.DATA_PREP,
    "data-prep-spare": TaskFamily.DATA_PREP,
    "causal-estimation": TaskFamily.CAUSAL_ESTIMATION,
    "causal-estimation-spare": TaskFamily.CAUSAL_ESTIMATION,
    "readout": TaskFamily.READOUT,
    "readout-spare": TaskFamily.READOUT
}

def get_task_family_for_agent(agent_id: str) -> TaskFamily:
    return AGENT_TO_FAMILY.get(agent_id, TaskFamily.DATA_PREP)

def localize_failure_cluster(cluster_traces: list[dict], db_file: str = "agentlab.db") -> dict:
    """
    Given a list of failed traces in a cluster, localizes the failure to the cause step.
    Returns a dict with cause_step, cause_agent_id, symptom_steps, and localization_basis.
    """
    if not cluster_traces:
        return {
            "cause_step": TaskFamily.DATA_PREP,
            "cause_agent_id": "unknown",
            "symptom_steps": [],
            "localization_basis": "no_data"
        }
        
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Track votes for which step was the root cause across all traces in the cluster
    cause_votes = {
        TaskFamily.DATA_PREP: 0,
        TaskFamily.CAUSAL_ESTIMATION: 0,
        TaskFamily.READOUT: 0
    }
    
    # Store evidence and bases
    bases = []
    agent_id_votes = {}
    all_symptom_steps = set()
    
    for trace in cluster_traces:
        req_id = trace["request_id"]
        
        # Query all signals for this request
        cursor.execute("""
            SELECT agent_id, kind, value, source, timestamp
            FROM signals
            WHERE request_id = ?
            ORDER BY timestamp ASC
        """, (req_id,))
        signals = cursor.fetchall()
        
        # Organize signals by task family
        family_signals = {
            TaskFamily.DATA_PREP: [],
            TaskFamily.CAUSAL_ESTIMATION: [],
            TaskFamily.READOUT: []
        }
        for sig in signals:
            agent_id = sig[0]
            kind = sig[1]
            val = sig[2]
            src = sig[3]
            tf = get_task_family_for_agent(agent_id)
            family_signals[tf].append({"kind": kind, "value": val, "source": src, "agent_id": agent_id})
            
        # Determine root cause step for this single trace
        trace_cause = None
        basis = "trace order"
        
        # Rule 1: Look for explicit oracle errors (out_of_bounds, tool_error)
        # Check Step 1 (Data Prep)
        if any(s["kind"] in ("tool_error", "malformed_handoff") for s in family_signals[TaskFamily.DATA_PREP]):
            trace_cause = TaskFamily.DATA_PREP
            basis = "oracle (tool_error/malformed_handoff)"
        # Check Step 2 (Causal Estimation)
        elif any(s["kind"] in ("out_of_bounds", "tool_error") for s in family_signals[TaskFamily.CAUSAL_ESTIMATION]):
            trace_cause = TaskFamily.CAUSAL_ESTIMATION
            basis = "oracle (out_of_bounds/tool_error)"
        # Check Step 3 (Readout)
        elif any(s["kind"] in ("tool_error", "refusal") for s in family_signals[TaskFamily.READOUT]):
            trace_cause = TaskFamily.READOUT
            basis = "oracle (tool_error/refusal)"
            
        # Rule 2: Check self-reports (diagnostic tool calls)
        if not trace_cause:
            if any(s["kind"] == "self_report" for s in family_signals[TaskFamily.DATA_PREP]):
                trace_cause = TaskFamily.DATA_PREP
                basis = "self_report"
            elif any(s["kind"] == "self_report" for s in family_signals[TaskFamily.CAUSAL_ESTIMATION]):
                trace_cause = TaskFamily.CAUSAL_ESTIMATION
                basis = "self_report"
            elif any(s["kind"] == "self_report" for s in family_signals[TaskFamily.READOUT]):
                trace_cause = TaskFamily.READOUT
                basis = "self_report"
                
        # Rule 3: Check soft classifiers/signal drift in order of execution
        if not trace_cause:
            if family_signals[TaskFamily.DATA_PREP]:
                trace_cause = TaskFamily.DATA_PREP
                basis = "signal drift"
            elif family_signals[TaskFamily.CAUSAL_ESTIMATION]:
                trace_cause = TaskFamily.CAUSAL_ESTIMATION
                basis = "signal drift"
            elif family_signals[TaskFamily.READOUT]:
                trace_cause = TaskFamily.READOUT
                basis = "signal drift"
                
        # Fallback to TaskFamily.DATA_PREP if no signals are triggered
        if not trace_cause:
            trace_cause = TaskFamily.DATA_PREP
            basis = "trace order"
            
        cause_votes[trace_cause] += 1
        bases.append(basis)
        
        # Track the agent_id of the cause step
        agents_for_step = [s["agent_id"] for s in family_signals[trace_cause]]
        if agents_for_step:
            agent_id = agents_for_step[0]
            agent_id_votes[agent_id] = agent_id_votes.get(agent_id, 0) + 1
            
        # Downstream steps that also had signals are considered symptom steps
        if trace_cause == TaskFamily.DATA_PREP:
            if family_signals[TaskFamily.CAUSAL_ESTIMATION]:
                all_symptom_steps.add(TaskFamily.CAUSAL_ESTIMATION)
            if family_signals[TaskFamily.READOUT]:
                all_symptom_steps.add(TaskFamily.READOUT)
        elif trace_cause == TaskFamily.CAUSAL_ESTIMATION:
            if family_signals[TaskFamily.READOUT]:
                all_symptom_steps.add(TaskFamily.READOUT)
                
    conn.close()
    
    # Aggregate consensus results
    consensus_cause = max(cause_votes, key=cause_votes.get)
    
    # Consensus agent_id
    if agent_id_votes:
        consensus_agent = max(agent_id_votes, key=agent_id_votes.get)
    else:
        # Fallback maps based on task family
        consensus_agent = "data-prep"
        if consensus_cause == TaskFamily.CAUSAL_ESTIMATION:
            consensus_agent = "causal-estimation"
        elif consensus_cause == TaskFamily.READOUT:
            consensus_agent = "readout"
            
    # Consensus localization basis (mode of bases)
    consensus_basis = max(set(bases), key=bases.count) if bases else "trace order"
    
    # Filter symptom steps (must be strictly downstream of cause step)
    symptoms = []
    if consensus_cause == TaskFamily.DATA_PREP:
        if TaskFamily.CAUSAL_ESTIMATION in all_symptom_steps:
            symptoms.append(TaskFamily.CAUSAL_ESTIMATION)
        if TaskFamily.READOUT in all_symptom_steps:
            symptoms.append(TaskFamily.READOUT)
    elif consensus_cause == TaskFamily.CAUSAL_ESTIMATION:
        if TaskFamily.READOUT in all_symptom_steps:
            symptoms.append(TaskFamily.READOUT)
            
    return {
        "cause_step": consensus_cause,
        "cause_agent_id": consensus_agent,
        "symptom_steps": symptoms,
        "localization_basis": consensus_basis
    }
