import re

from common.schema import AgentResponse


def score_end_state(response: AgentResponse, expected: str) -> bool:
    """
    Compares the final text output to the expected value.
    For causal estimation tasks, extracts numerical lift estimates and checks boundaries.
    """
    output = response.output

    # If the expected value is formatted as a percentage lift (e.g. "+2.4%"),
    # we extract the floats and perform a numeric bounds check.
    pct_match_exp = re.search(r"([+-]?\d+\.?\d*)\s*%", expected)
    pct_match_out = re.search(r"([+-]?\d+\.?\d*)\s*%", output)

    if pct_match_exp and pct_match_out:
        val_exp = float(pct_match_exp.group(1))
        val_out = float(pct_match_out.group(1))
        # Within +/- 1% tolerance
        return abs(val_exp - val_out) < 1.0

    # Otherwise, perform standard substring match
    return expected.strip().lower() in output.strip().lower()
