import os
import re
from datetime import datetime
from common.config import settings
from common.schema import Signal

# Saved models location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVED_MODELS_DIR = os.path.join(BASE_DIR, "saved_models")

# Heuristic keyword matching for Mock/Fallback mode (extremely fast & robust)
HEURISTIC_PATTERNS = {
    "refusal": [
        r"cannot\s+(?:fulfill|comply|help|process|answer)",
        r"as\s+an\s+ai",
        r"unable\s+to\s+(?:process|fulfill|generate|comply)",
        r"sorry,\s+but\s+i\s+cannot"
    ],
    "task_failure": [
        r"exception\s+occurred",
        r"failed\s+to\s+(?:parse|validate|execute|calculate)",
        r"traceback\s+\(most\s+recent\s+call\s+last\)",
        r"invalid\s+(?:format|input|syntax)",
        r"(?:fatal\s+)?error",
        r"division\s+by\s+zero"
    ],
    "low_confidence_output": [
        r"low\s+confidence",
        r"not\s+(?:sure|confident)",
        r"unreliable",
        r"high\s+variance",
        r"possibly\s+incorrect",
        r"out\s+of\s+bounds",
        r"extreme"
    ],
    "malformed_handoff": [
        r"missing\s+(?:required\s+)?key",
        r"malformed\s+(?:input|output|json|handoff)",
        r"handoff\s+failed",
        r"invalid\s+transition"
    ]
}

# In-memory model cache for real mode
_LOADED_MODELS = {}

def load_model_and_tokenizer(kind: str):
    """Loads and caches the model/tokenizer for the given failure kind."""
    if kind in _LOADED_MODELS:
        return _LOADED_MODELS[kind]
        
    model_path = os.path.join(SAVED_MODELS_DIR, kind)
    if not os.path.isdir(model_path) or os.path.exists(os.path.join(model_path, "dummy.txt")):
        # Model path is missing or it is a dummy placeholder, return None to trigger fallback
        return None
        
    try:
        import torch
        from transformers import DistilBertTokenizer, DistilBertForSequenceClassification
        
        tokenizer = DistilBertTokenizer.from_pretrained(model_path)
        model = DistilBertForSequenceClassification.from_pretrained(model_path)
        model.eval()
        _LOADED_MODELS[kind] = (model, tokenizer)
        return model, tokenizer
    except ImportError:
        print(f"[infer] Warning: torch or transformers not installed. Falling back to heuristics.")
        return None
    except Exception as e:
        print(f"[infer] Warning: Failed to load real model for {kind}: {e}. Falling back to heuristics.")
        return None

def infer_signals(
    request_id: str,
    agent_id: str,
    output: str,
    timestamp: datetime = None
) -> list[Signal]:
    """
    Classifies the agent output using 4 binary classifiers.
    Returns a list of Signal objects for any positive classification.
    """
    if timestamp is None:
        timestamp = datetime.utcnow()
        
    signals = []
    
    # We classify for each of the four categories
    categories = ["refusal", "task_failure", "low_confidence_output", "malformed_handoff"]
    
    for kind in categories:
        is_positive = False
        
        # 1. Try real neural net classification first if mock=false
        if not settings.mock:
            resources = load_model_and_tokenizer(kind)
            if resources is not None:
                model, tokenizer = resources
                try:
                    import torch
                    inputs = tokenizer(
                        output,
                        return_tensors="pt",
                        truncation=True,
                        max_length=128,
                        padding=True
                    )
                    with torch.no_grad():
                        logits = model(**inputs).logits
                        probs = torch.softmax(logits, dim=-1)
                        # Label 1 is failure, label 0 is non-failure
                        pred_label = torch.argmax(probs, dim=-1).item()
                        if pred_label == 1:
                            is_positive = True
                except Exception as e:
                    print(f"[infer] Inference error: {e}")
                    
        # 2. Fallback to heuristic rules (used in MOCK=true, or if model load fails)
        if not is_positive:
            # Check heuristic regexes
            patterns = HEURISTIC_PATTERNS[kind]
            for pat in patterns:
                if re.search(pat, output, re.IGNORECASE):
                    is_positive = True
                    break
                    
        if is_positive:
            signals.append(Signal(
                request_id=request_id,
                agent_id=agent_id,
                timestamp=timestamp,
                kind=kind,
                value=1.0,
                source="classifier"
            ))
            
    return signals
