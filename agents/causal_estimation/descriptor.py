from common.schema import AgentDescriptor, Platform, TaskFamily


def get_descriptor() -> AgentDescriptor:
    return AgentDescriptor(
        agent_id="causal-estimation",
        display_name="Causal Estimation",
        platform=Platform.AWS_AGENTCORE,
        task_families=[TaskFamily.CAUSAL_ESTIMATION],
        capability_text=(
            "Estimates treatment effect (ATE) using CUPED variance reduction, "
            "evaluates confidence intervals, and flags heterogeneous treatment effects."
        ),
        cost_per_1k_tokens=0.015,
        endpoint=None,
        external_id=None
    )
