from common.schema import AgentDescriptor, Platform, TaskFamily


def get_descriptor() -> AgentDescriptor:
    return AgentDescriptor(
        agent_id="data-prep",
        display_name="Data Prep",
        platform=Platform.GCP_ADK,
        task_families=[TaskFamily.DATA_PREP],
        capability_text=(
            "Pulls A/B experiment raw event data from Google BigQuery, "
            "performs sample ratio mismatch (SRM) checks, and validates "
            "randomization integrity."
        ),
        cost_per_1k_tokens=0.000075,
        endpoint=None,
        external_id=None
    )
