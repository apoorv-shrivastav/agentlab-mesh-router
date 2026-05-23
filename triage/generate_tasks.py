import json
from common.config import settings
from common.schema import TaskFamily

# High-fidelity mock responses for task generation
MOCK_RESPONSES = {
    TaskFamily.DATA_PREP: {
        "root_cause": "SRM check failed to catch randomization drift on highly skewed target population.",
        "proposed_tasks": [
            {
                "prompt": "Run SRM validation on dataset with intentional 55/45 allocation split.",
                "expected": "SRM check: FAILED"
            },
            {
                "prompt": "Evaluate data randomization integrity with missing covariate column values.",
                "expected": "SRM check: SRM validation error"
            },
            {
                "prompt": "Validate randomization mapping for high volume user cohorts (100k+).",
                "expected": "SRM check: PASSED"
            }
        ]
    },
    TaskFamily.CAUSAL_ESTIMATION: {
        "root_cause": "CUPED covariate adjustment yielded extreme variance and outlier lift estimate (+48.5%).",
        "proposed_tasks": [
            {
                "prompt": "Compute CUPED-adjusted lift on dataset with high pre-period variance.",
                "expected": "Causal estimate: Lift falls within expected range [0.0, 5.0%]"
            },
            {
                "prompt": "Verify causal lift estimation when treatment group is significantly smaller than control.",
                "expected": "Causal estimate: Lift point estimate is robust"
            },
            {
                "prompt": "Estimate ATE when outlier covariate values skew regression coefficients.",
                "expected": "Causal estimate: ATE point estimate within bounds"
            }
        ]
    },
    TaskFamily.READOUT: {
        "root_cause": "Readout memo overstates certainty and recommends ship despite wide confidence intervals.",
        "proposed_tasks": [
            {
                "prompt": "Generate stakeholder recommendation memo for ATE of +1.2% and CI of [-1.0%, +3.4%].",
                "expected": "Memo output: Recommend NO SHIP or hold (neutral/negative bound)"
            },
            {
                "prompt": "Draft product readout memo with wide CI bounds and high variance.",
                "expected": "Memo output: Clearly state high uncertainty and recommend further test collection"
            }
        ]
    }
}

def generate_triage_tasks(
    cause_step: TaskFamily,
    cluster_traces: list[dict],
    localization_basis: str
) -> dict:
    """
    Calls Gemini 3.5 Flash to generate a one-line root cause and 3-5 proposed eval tasks.
    Falls back to mock responses in MOCK mode or if Vertex AI is unavailable.
    """
    # 1. Heuristic/Mock Mode
    if settings.mock:
        return MOCK_RESPONSES.get(cause_step, MOCK_RESPONSES[TaskFamily.DATA_PREP])
        
    # 2. Real Mode: Call Vertex AI / Gemini 3.5 Flash
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel, GenerationConfig
        
        # Initialize Vertex AI
        vertexai.init(project=settings.gcp.project_id, region=settings.gcp.region)
        model = GenerativeModel("gemini-1.5-flash") # standard Flash model name
        
        # Construct failure trace snippets for prompt context
        trace_contexts = []
        for t in cluster_traces[:5]: # Include up to 5 traces to fit prompt context
            trace_contexts.append(f"Request ID: {t['request_id']}\nOutputs:\n{t['combined_text']}\n")
            
        prompt = f"""
        You are the AgentLab Triage Agent. A pipeline regression occurred on step: {cause_step.value}.
        Localization basis: {localization_basis}.
        
        Here are traces from the failure cluster:
        ---
        {"---".join(trace_contexts)}
        ---
        
        Analyze the failure traces and generate a structured JSON response containing:
        1. "root_cause": A one-line natural-language summary explaining what failed.
        2. "proposed_tasks": A list of 3 new evaluation cases. Each case is a dictionary with:
           - "prompt": The testing prompt targeting the specific failure condition.
           - "expected": The expected outcome (e.g. correct bounds, robust estimate, refusal/check status).
           
        JSON Format example:
        {{
            "root_cause": "Detailed description of the issue.",
            "proposed_tasks": [
                {{"prompt": "Run test on skew...", "expected": "SRM: FAILED"}}
            ]
        }}
        """
        
        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(
                response_mime_type="application/json",
                temperature=0.2
            )
        )
        
        data = json.loads(response.text)
        return {
            "root_cause": data.get("root_cause", "Unexplained pipeline regression."),
            "proposed_tasks": data.get("proposed_tasks", [])
        }
    except Exception as e:
        print(f"[generate_tasks] Warning: Gemini model call failed: {e}. Falling back to mock data.")
        return MOCK_RESPONSES.get(cause_step, MOCK_RESPONSES[TaskFamily.DATA_PREP])
