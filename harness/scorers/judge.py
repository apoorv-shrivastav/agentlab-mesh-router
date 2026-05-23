import random

from common.config import settings
from common.schema import AgentResponse


def run_llm_judge(
    response: AgentResponse,
    rubric: str,
    expected: str,
    randomize_order: bool = True
) -> bool:
    """
    Evaluates the quality of open-ended outputs using LLM-as-a-judge.
    In MOCK=true mode, performs standard expected substring checks.
    In MOCK=false mode, targets the Gemini Flash model to evaluate based on a rubric.
    """
    if settings.mock:
        # Simulate LLM judge grading based on keyword presence
        return expected.strip().lower() in response.output.strip().lower()

    # Real evaluation pathway
    try:
        from google import genai
        # Initialize Google Gen AI client
        client = genai.Client(project=settings.gcp.project_id)

        prompt = f"""
        Evaluate the following agent output against the rubric and the expected result.

        Expected Key Rationale: {expected}
        Rubric: {rubric}
        Agent Output: {response.output}

        Is the output correct according to the rubric? Respond with exactly 'YES' or 'NO'.
        """

        # Simple randomized padding to prevent order biases if evaluating pairwise
        # (for demo / evaluation setup)
        if randomize_order:
            padding = f"\n[Eval ID: {random.randint(1000, 9999)}]"
            prompt += padding

        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        verdict = resp.text.strip().upper()
        return "YES" in verdict
    except Exception as e:
        # Fallback to simple matching if API call fails
        print(f"[Judge Error] Fallback to simple match: {e}")
        return expected.strip().lower() in response.output.strip().lower()
