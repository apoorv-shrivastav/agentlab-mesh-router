#!/bin/bash
# AWS AgentCore and Online Evaluation setup helper script
# This script should be run after the mesh-causal-agent container is built and pushed (Milestone 7).

set -e

# Load environment variables if they exist
if [ -f ../.env ]; then
  source ../.env
elif [ -f .env ]; then
  source .env
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)
AGENTCORE_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/MeshAgentCoreExecutionRole"

echo "=== AWS AgentCore Setup ==="
echo "Using AWS Account: $AWS_ACCOUNT_ID"
echo "Using Execution Role: $AGENTCORE_ROLE_ARN"

# 1. Create the agent runtime
echo "Creating Bedrock AgentCore runtime: mesh-causal-agent..."
aws bedrock-agentcore-control create-agent-runtime \
    --agent-runtime-name "mesh-causal-agent" \
    --description "Causal-estimation agent for the AgentLab demo" \
    --execution-role-arn "$AGENTCORE_ROLE_ARN" \
    --network-configuration "publicNetwork={}" \
    --container-configuration file://../infra/aws/agentcore_container.json

AGENTCORE_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:${AWS_ACCOUNT_ID}:agent-runtime/mesh-causal-agent"
echo "AgentCore Runtime ARN: $AGENTCORE_RUNTIME_ARN"

# 2. Create online evaluation config
echo "Creating Bedrock Online Evaluation configuration..."
aws bedrock-agentcore-control create-online-evaluation-config \
    --online-evaluation-config-name "mesh-causal-eval" \
    --description "Continuous quality evaluation for the AgentLab causal-estimation agent" \
    --rule '{
        "samplingConfig": { "samplingPercentage": 10.0 },
        "filters": []
    }' \
    --data-source-config '{
        "agentEndpoint": "'$AGENTCORE_RUNTIME_ARN'/endpoint/DEFAULT"
    }' \
    --evaluators '[
        {"evaluatorId": "task_completion", "type": "BUILT_IN"},
        {"evaluatorId": "safety", "type": "BUILT_IN"}
    ]'

echo "AWS AgentCore resources successfully provisioned!"
