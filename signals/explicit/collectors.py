from datetime import datetime
from common.schema import Signal

def collect_explicit_signals(
    request_id: str,
    agent_id: str,
    latency_ms: float,
    tokens_in: int,
    tokens_out: int,
    cost_per_1k: float,
    tool_calls: list[dict] = None,
    handoff_failed: bool = False,
    timestamp: datetime = None
) -> list[Signal]:
    """
    Collects and extracts explicit signals from run metrics, tool calls, and handoff status.
    Returns a list of Signal instances.
    """
    if timestamp is None:
        timestamp = datetime.utcnow()
        
    signals = []
    
    # 1. Latency signal (raw value in ms)
    signals.append(Signal(
        request_id=request_id,
        agent_id=agent_id,
        timestamp=timestamp,
        kind="latency",
        value=float(latency_ms),
        source="explicit"
    ))
    
    # 2. Cost signal (raw cost value)
    cost = float(tokens_in + tokens_out) * (cost_per_1k / 1000.0)
    signals.append(Signal(
        request_id=request_id,
        agent_id=agent_id,
        timestamp=timestamp,
        kind="cost",
        value=cost,
        source="explicit"
    ))
    
    # 3. Tool errors
    if tool_calls:
        has_tool_error = False
        for tc in tool_calls:
            # Check if there is an error key or if the output indicates an error/exception
            if "error" in tc or tc.get("status") in ("error", "failure", "failed"):
                has_tool_error = True
                break
        
        if has_tool_error:
            signals.append(Signal(
                request_id=request_id,
                agent_id=agent_id,
                timestamp=timestamp,
                kind="tool_error",
                value=1.0,
                source="explicit"
            ))
            
    # 4. Handoff failures
    if handoff_failed:
        signals.append(Signal(
            request_id=request_id,
            agent_id=agent_id,
            timestamp=timestamp,
            kind="malformed_handoff",
            value=1.0,
            source="explicit"
        ))
        
    return signals
