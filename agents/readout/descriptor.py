from common.schema import AgentDescriptor, Platform, TaskFamily


def get_descriptor() -> AgentDescriptor:
    return AgentDescriptor(
        agent_id="readout",
        display_name="Readout & Recommendation",
        platform=Platform.AZURE_OPENAI,
        task_families=[TaskFamily.READOUT],
        capability_text=(
            "Drafts the stakeholder-ready 'ship / don't ship / iterate' memo "
            "synthesizing data validation checks and causal estimation outputs."
        ),
        cost_per_1k_tokens=0.010,
        endpoint=None,
        external_id=None
    )
