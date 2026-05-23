from common.schema import AgentDescriptor, Platform, TaskFamily


def test_imports_and_schemas():
    assert AgentDescriptor is not None
    assert Platform.GCP_ADK == "gcp_adk"
    assert TaskFamily.DATA_PREP == "data_prep"
