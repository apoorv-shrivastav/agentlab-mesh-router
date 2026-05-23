import re
from datetime import datetime
from common.schema import Signal

# Regex patterns for common failure modes
FAILURE_PATTERNS = {
    "refusal": [
        r"(?i)\bi\s+cannot\s+(?:fulfill|comply|help|process|answer)\b",
        r"(?i)\bas\s+an\s+ai\b",
        r"(?i)\bunable\s+to\s+(?:process|fulfill|generate|comply)\b",
        r"(?i)\bsorry,\s+but\s+i\s+cannot\b"
    ],
    "task_failure": [
        r"(?i)\bexception\s+occurred\b",
        r"(?i)\bfailed\s+to\s+(?:parse|validate|execute|calculate)\b",
        r"(?i)\btraceback\s+\(most\s+recent\s+call\s+last\)\b",
        r"(?i)\binvalid\s+(?:format|input|syntax)\b",
        r"(?i)\b(?:fatal\s+)?error\b"
    ],
    "low_confidence_output": [
        r"(?i)\blow\s+confidence\b",
        r"(?i)\bnot\s+(?:sure|confident)\b",
        r"(?i)\bunreliable\b",
        r"(?i)\bhigh\s+variance\b",
        r"(?i)\bpossibly\s+incorrect\b",
        r"(?i)\bout\s+of\s+bounds\b"
    ],
    "malformed_handoff": [
        r"(?i)\bmissing\s+(?:required\s+)?key\b",
        r"(?i)\bmalformed\s+(?:input|output|json|handoff)\b",
        r"(?i)\bhandoff\s+failed\b",
        r"(?i)\binvalid\s+transition\b"
    ]
}

def extract_regex_signals(
    request_id: str,
    agent_id: str,
    output: str,
    timestamp: datetime = None
) -> list[Signal]:
    """
    Scans the agent output for failure keyword/phrase regex patterns.
    Returns a list of Signal objects for any matching failure kinds.
    """
    if timestamp is None:
        timestamp = datetime.utcnow()
    
    signals = []
    
    for kind, patterns in FAILURE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, output):
                signals.append(Signal(
                    request_id=request_id,
                    agent_id=agent_id,
                    timestamp=timestamp,
                    kind=kind,
                    value=1.0,
                    source="regex"
                ))
                break # Only log one signal per kind even if multiple patterns match
                
    return signals
