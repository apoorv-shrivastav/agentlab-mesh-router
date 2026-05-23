import os
import time

from common.schema import AgentResponse

# A2A Handoff channel simulating cloud A2A agent interfaces.
# If SEQUENTIAL=true is set, it falls back to sequential execution in-process.
SEQUENTIAL_FALLBACK = os.getenv("SEQUENTIAL", "true").lower() in ("true", "1", "yes")

def handoff_data(
    source_step: str,
    target_step: str,
    response: AgentResponse
) -> str:
    """
    Simulates sending intermediate state from source agent step to target agent step.
    Under SEQUENTIAL_FALLBACK, it formats the output of the source step directly
    into the prompt context of the next step.
    """
    if SEQUENTIAL_FALLBACK:
        # In sequential fallback mode, we pass the output directly through memory.
        # Print transition info
        print(
            f"[A2A Handoff (Fallback)] Forwarding output of '{source_step}' "
            f"to '{target_step}' directly."
        )
        return f"Input from preceding step ({source_step}):\n---\n{response.output}\n---\n"
    else:
        # Simulate network delay of cross-cloud A2A agent mesh
        time.sleep(0.05)
        print(
            f"[A2A Handoff (Mesh)] Transmitting payload from '{source_step}' "
            f"to '{target_step}' via cloud mesh."
        )
        return (
            f"Input from preceding step ({source_step}) received via mesh:\n"
            f"---\n{response.output}\n---\n"
        )
