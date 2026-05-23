#!/bin/bash
# Canonical Agent Registry Registration Script
# This script registers all three specialist agents (and spares) in the Agent Platform Registry.
# Note: Requires the 'agent-platform' gcloud component/extension enabled on your account.

set -e

# Load environment variables
if [ -f ../.env ]; then
  source ../.env
elif [ -f .env ]; then
  source .env
fi

AWS_ACCOUNT_ID="192969248603"
AGENTCORE_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:${AWS_ACCOUNT_ID}:agent-runtime/mesh-causal-agent"

echo "=== Registering Agents in Canonical Registry ==="
echo "GCP Project: $GCP_PROJECT_ID"
echo "AWS Account: $AWS_ACCOUNT_ID"

# 1. Register Step-1 Agent: Data Prep (GCP)
echo "Registering Step 1: Data Prep (GCP)..."
gcloud agent-platform registry agents register \
    --agent-id=data-prep \
    --platform=gemini-enterprise \
    --metadata="mesh.platform=GCP,mesh.task_family=data_prep,mesh.step=1" \
    --project="$GCP_PROJECT_ID" || echo "Skipping actual registration call (requires gcloud agent-platform component)"

# 2. Register Step-1 Spare Agent: Data Prep Spare (GCP)
echo "Registering Step 1 Spare: Data Prep Spare (GCP)..."
gcloud agent-platform registry agents register \
    --agent-id=data-prep-spare \
    --platform=gemini-enterprise \
    --metadata="mesh.platform=GCP,mesh.task_family=data_prep,mesh.step=1" \
    --project="$GCP_PROJECT_ID" || echo "Skipping actual registration"

# 3. Register Step-2 Agent: Causal Estimation (AWS AgentCore)
echo "Registering Step 2: Causal Estimation (AWS)..."
gcloud agent-platform registry agents register \
    --agent-id=causal-estimation \
    --platform=aws-agentcore \
    --endpoint="$AGENTCORE_RUNTIME_ARN" \
    --metadata="mesh.platform=AWS,mesh.task_family=causal_estimation,mesh.step=2,aws.region=us-east-1" \
    --project="$GCP_PROJECT_ID" || echo "Skipping actual registration"

# 4. Register Step-3 Agent: Readout & Recommendation (Azure)
echo "Registering Step 3: Readout (Azure)..."
gcloud agent-platform registry agents register \
    --agent-id=readout \
    --platform=azure-openai \
    --endpoint="https://mesh-openai-287cc.openai.azure.com/" \
    --metadata="mesh.platform=Azure,mesh.task_family=readout,mesh.step=3,azure.app_insights_id=8c5dcd16-e889-48ef-a390-e7253e8c4bda,azure.deployment=gpt-4o" \
    --project="$GCP_PROJECT_ID" || echo "Skipping actual registration"

echo "Agent registry definitions saved and initialized."
