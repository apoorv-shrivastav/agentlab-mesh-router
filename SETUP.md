# SETUP.md — Three-Cloud Setup

Step-by-step instructions for standing up AgentLab across **Google Cloud + AWS + Azure**. Written for someone comfortable with Google Cloud but newer to AWS and Azure. Every section calls out the *why* before the *what*, lists pitfalls, and gives concrete commands.

**Estimated time**: 6–8 hours of focused work spread across 2 evenings. Budget aggressively; do not try to do all three clouds in one sitting.

> **Naming.** The product is **AgentLab**. The cloud resource names in this guide use the `mesh-` prefix (`mesh-router`, `mesh-causal-agent`, the `mesh` BigQuery dataset, `mesh-router-sa`, `MESH_ROUTER_URL`, etc.). That prefix is the *infrastructure namespace* — it is deliberately kept stable so the commands here, in `TEARDOWN.md`, and in any infra you have already provisioned all match. Do not rename these to "agentlab" for cosmetic consistency; a half-renamed infra layer is worse than a clearly-scoped one. The rule: `mesh-*` = infrastructure, **AgentLab** = the product and everything user-facing (the console, README, pitch).

**Estimated cost on the cheap-cloud path (May 14 – May 25)**: roughly **$95 total** economically, of which only ~$45–50 is real out-of-pocket spend once GCP's $300 and Azure's $200 free credits are applied. Detailed cost notes in [Cost Notes](#cost-notes) at the bottom.

> **Read this before you start.** This guide sets up *infrastructure*. It assumes a *codebase* that does not exist until you scaffold it with [`SCAFFOLD.md`](SCAFFOLD.md). The correct overall sequence is: (1) the account/credential/resource bootstrap in this guide — Parts 1–3 up to the point each one says "deferred"; (2) scaffold and build the codebase in MOCK mode via SCAFFOLD.md Milestones 0–6; (3) come back for the deferred deploy steps here, alongside SCAFFOLD.md Milestone 7. Several steps in Parts 2 and 4 are explicitly marked *deferred* because they need agent containers that the codebase produces. Do not try to run them early — they will block.

> **Security — applies to every command in this guide.** Never paste a key, secret, access-key, connection string, or `xoxb-` token into a chat with an AI agent, into a commit, or into any shared doc. The commands below are deliberately written to pipe secrets straight into a secret manager (`... | gcloud secrets create ...`) so they are never printed. Endpoints, ARNs, project IDs, and resource names are *not* secrets — those are safe to share. If a secret is ever exposed, rotate it immediately. A coding agent asking you to "share your admin credentials so I can run this" should always be declined — use CloudShell or a secret manager instead.

---

## Suggested Order

Do not jump around. The dependencies look like this:

1. **GCP first** (longest section; foundation everything else federates *into*) → ~3–4 hours
2. **AWS second** (Bedrock AgentCore is the trickier of the two adjacent clouds) → ~2 hours
3. **Azure third** (Azure OpenAI is mostly CLI; watch for quota/region snags) → ~1.5 hours
4. **Console deployment last** (depends on all three above being live) → ~45 minutes

A "Day 1 / Day 2 / Day 3" schedule appears at the [end of this document](#suggested-schedule).

---

## What You Need Before Starting

- [ ] A Google account with billing enabled (any personal Gmail works)
- [ ] An AWS account (sign up at `aws.amazon.com`; free tier eligible accounts work but Bedrock costs money regardless)
- [ ] A Microsoft account, Azure subscription (sign up at `azure.microsoft.com`; new accounts get $200 free credit)
- [ ] A credit card that you'll attach to all three (the free credits cover most of the cost but a card is required)
- [ ] On your laptop: `gcloud`, `aws`, `az` CLIs installed; Docker Desktop; Node 20+; Python 3.11+; `terraform` 1.6+; `pnpm`
- [ ] A GitHub account (you have one)
- [ ] One spare Slack workspace for the A2UI demo surface — use any Slack you control, or `slack.com/get-started` for a new one (free)

Quick install commands if you're missing any:

```bash
# macOS via Homebrew
brew install --cask google-cloud-sdk
brew install awscli
brew install azure-cli
brew install --cask docker
brew install node@20 python@3.11 terraform pnpm

# Verify
gcloud --version && aws --version && az --version && terraform --version
```

---

## Part 1 — Google Cloud

This is the longest section because GCP is the *canonical* cloud — AgentLab runs here, the federated registry lives here, BigQuery is the signal store, and the console is hosted here. Everything else federates into this.

### 1.1 Create the Project

```bash
# Replace with a globally unique ID
export GCP_PROJECT_ID="agentlab-mesh-$(date +%s)"

gcloud auth login
gcloud projects create $GCP_PROJECT_ID --name="AgentLab"
gcloud config set project $GCP_PROJECT_ID
```

Now link a billing account. If this is your first GCP project you'll need to attach a billing account in the console: `console.cloud.google.com/billing` → Manage billing accounts → link to the project.

Alternative one-liner if you know your billing account ID:

```bash
gcloud beta billing accounts list  # find your ID
gcloud beta billing projects link $GCP_PROJECT_ID --billing-account=XXXXXX-XXXXXX-XXXXXX
```

### 1.2 Enable APIs

These are the GCP APIs AgentLab depends on. Enable them all up front — there are about 14 — so you don't trip over a missing API mid-build.

```bash
gcloud services enable \
    aiplatform.googleapis.com \
    bigquery.googleapis.com \
    bigqueryconnection.googleapis.com \
    cloudbuild.googleapis.com \
    cloudtrace.googleapis.com \
    compute.googleapis.com \
    container.googleapis.com \
    iam.googleapis.com \
    iamcredentials.googleapis.com \
    logging.googleapis.com \
    monitoring.googleapis.com \
    pubsub.googleapis.com \
    run.googleapis.com \
    secretmanager.googleapis.com \
    storage.googleapis.com \
    --project=$GCP_PROJECT_ID
```

Then enable Gemini Enterprise Agent Platform (this used to be Vertex AI; the Cloud Next '26 keynote evolved it):

Go to `console.cloud.google.com/vertex-ai`, accept the agent platform terms when prompted. Confirm Agent Registry, Agent Identity, Agent Gateway, and Agent Evaluation all show up under "Agent Platform" in the left nav.

> **Pitfall**: If you see "billing not enabled" errors when calling Vertex APIs even after enabling billing on the project, wait 10 minutes. Sometimes the billing propagation lags.

### 1.3 Set Up the Region and Default Service Account

```bash
export GCP_REGION="us-central1"
gcloud config set compute/region $GCP_REGION
gcloud config set run/region $GCP_REGION

# Create the service account Mesh services will run as
gcloud iam service-accounts create mesh-router-sa \
    --display-name="AgentLab service account" \
    --project=$GCP_PROJECT_ID

export SA_EMAIL="mesh-router-sa@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

# Grant the roles Mesh actually needs (least-privilege; do not use Editor)
for role in \
    roles/aiplatform.user \
    roles/bigquery.dataEditor \
    roles/bigquery.jobUser \
    roles/cloudtrace.agent \
    roles/logging.logWriter \
    roles/monitoring.metricWriter \
    roles/pubsub.editor \
    roles/run.invoker \
    roles/secretmanager.secretAccessor \
    roles/storage.objectViewer
do
    gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="$role" \
        --quiet
done
```

### 1.4 Create the BigQuery Datasets

BigQuery is where federated signals from all three clouds land. Two datasets: one for raw federated signals, one for the eval task store.

```bash
bq --location=US mk --dataset \
    --description="Federated agent signals from GCP, AWS, Azure" \
    ${GCP_PROJECT_ID}:mesh

bq --location=US mk --dataset \
    --description="Eval task golden sets, versioned" \
    ${GCP_PROJECT_ID}:evals
```

The actual table schemas are created by Terraform in the next step. The dataset shells are created here so Terraform doesn't fight over dataset creation permissions.

### 1.5 Vector Search — BigQuery (default, free) or AlloyDB (production swap)

The router does nearest-neighbor lookups over agent capability embeddings. You have two options.

**Default for the hackathon — BigQuery vector search.** Zero standing cost, nothing to provision, no instance to remember to delete. Embeddings live in a BigQuery table; lookups use the native `VECTOR_SEARCH` function. Latency is ~100–300ms, which is invisible for a demo of this size. The table is created by Terraform in the next step — there is *nothing to do here* on the cheap path. Skip to § 1.6.

**Optional production swap — AlloyDB AI.** AlloyDB AI with `pgvector` is the keynote-blessed vector store and gets you sub-50ms lookups. It costs roughly **$12/day while running** and is the single most expensive resource in this guide. Only do this if you specifically want to show it in the demo or quote a sub-50ms latency number. If you do:

```bash
gcloud alloydb clusters create mesh-cluster \
    --password="$(openssl rand -base64 24)" \
    --region=$GCP_REGION \
    --project=$GCP_PROJECT_ID

echo -n "PASTE_THE_PASSWORD_YOU_JUST_GENERATED" | \
    gcloud secrets create alloydb-password \
    --data-file=- --project=$GCP_PROJECT_ID

gcloud alloydb instances create mesh-primary \
    --instance-type=PRIMARY --cpu-count=2 \
    --region=$GCP_REGION --cluster=mesh-cluster \
    --project=$GCP_PROJECT_ID
```

> **If you take the AlloyDB path**: delete the *instance* (not just the cluster) the night of the demo — see the cleanup checklist. The README documents AlloyDB as the production swap, so mentioning in the demo that "the demo runs BigQuery vector search; AlloyDB AI is the documented production upgrade" is a good senior-engineering signal either way.

### 1.6 Create the Pub/Sub Topics

Mesh uses three Pub/Sub topics:

```bash
gcloud pubsub topics create mesh-router-decisions --project=$GCP_PROJECT_ID
gcloud pubsub topics create mesh-signal-alerts --project=$GCP_PROJECT_ID
gcloud pubsub topics create mesh-triage-proposals --project=$GCP_PROJECT_ID
```

### 1.7 Provision OAuth and a Slack App

The A2UI Slack surface needs a Slack app to post alerts and the approval flow.

1. Go to `api.slack.com/apps`. Click "Create New App" → "From scratch". Name it "AgentLab".
2. Pick the workspace you set aside for the demo.
3. Under "OAuth & Permissions", add these bot scopes: `chat:write`, `chat:write.public`, `commands`, `users:read`.
4. Install to workspace. Copy the Bot User OAuth Token (starts with `xoxb-`). Save it:

```bash
echo -n "PASTE_YOUR_xoxb_TOKEN" | \
    gcloud secrets create slack-bot-token \
    --data-file=- --project=$GCP_PROJECT_ID
```

5. Under "Interactivity & Shortcuts", enable interactivity and set the Request URL to a placeholder — we'll set the real Cloud Run URL later.
6. Under "Slash Commands", add `/mesh` pointing to that same Cloud Run URL placeholder.

### 1.8 Deploy the Step-1 Agent: Data Prep (GCP)

Step 1 of the workflow — pulls the experiment's event data, runs the sample-ratio-mismatch check, validates randomization. It lives on GCP because the product-analytics warehouse is BigQuery.

```bash
cd agents/data_prep
# (the agent code is in the repo, built per SCAFFOLD.md Milestone 1)
gcloud agent-platform agents deploy \
    --agent-config=adk_config.yaml \
    --display-name="Data Prep" \
    --service-account=$SA_EMAIL \
    --region=$GCP_REGION \
    --project=$GCP_PROJECT_ID

# Register in the canonical Agent Registry
gcloud agent-platform registry agents register \
    --agent-id=data-prep \
    --platform=gemini-enterprise \
    --metadata="mesh.platform=GCP,mesh.task_family=data_prep,mesh.step=1"
```

The orchestrator (hub) is deployed the same way from `orchestrator/` once the codebase is built — it carries the router and drives the three-step workflow.

> A second GCP-hosted "spare" data-prep agent (from `agents/spares/`) should also be registered — the router needs a healthy alternate to reroute a degraded step to. Register it with `--agent-id=data-prep-spare` and the same task-family metadata.

### 1.9 Deploy the Step-2 Agent: Causal Estimation (AWS)

Step 2 — the causal effect estimation — is deferred to Part 2 (AWS). In the cross-cloud story this is the *external experimentation vendor's* agent; it runs on AWS AgentCore. See § 2.3. There is nothing to do on GCP for this step.

The Step-3 readout agent runs on Azure — see Part 3.

### 1.10 Save the GCP Environment File

Drop a file in your repo root (gitignored) capturing the GCP side of the environment:

```bash
cat > .env.gcp <<EOF
GCP_PROJECT_ID=$GCP_PROJECT_ID
GCP_REGION=$GCP_REGION
SA_EMAIL=$SA_EMAIL
VECTOR_BACKEND=bigquery
BIGQUERY_DATASET_SIGNALS=mesh
BIGQUERY_DATASET_EVALS=evals
# If you took the AlloyDB swap, instead set:
# VECTOR_BACKEND=alloydb
# ALLOYDB_CLUSTER=mesh-cluster
# ALLOYDB_INSTANCE=mesh-primary
EOF

echo ".env.*" >> .gitignore
```

**You are done with GCP. Take a break.** When you come back, AWS is next.

---

## Part 2 — Amazon Web Services

AWS hosts the Step-2 agent — **causal estimation** — on Bedrock AgentCore. In the workflow's story this is the external experimentation vendor's agent: you don't control its cloud or its model. AgentLab consumes AWS via the Bedrock control plane API and CloudWatch logs; AWS is read-mostly.

### 2.1 Create the AWS Account and IAM User

If you don't already have an AWS account, sign up at `aws.amazon.com/free`. Use a credit card — the free tier covers a lot but Bedrock specifically is not free-tier eligible.

```bash
# After account creation, in the AWS console go to IAM → Users → Create user
# Name: mesh-router-cross-cloud
# Permissions: attach the following managed policies:
#   - AmazonBedrockFullAccess
#   - CloudWatchLogsReadOnlyAccess
# Then create an access key for "Other" use case
# Download the CSV with the access key ID and secret

aws configure
# AWS Access Key ID: <paste from CSV>
# AWS Secret Access Key: <paste from CSV>
# Default region: us-east-1   ← important; AgentCore is most mature in us-east-1
# Default output: json

# Verify
aws sts get-caller-identity
```

> **Pitfall**: AgentCore is available in `us-east-1`, `us-west-2`, and a couple of EU regions. **Pick `us-east-1`** for the hackathon — most documentation and tutorials assume it.

### 2.2 Bedrock Model Access

The old "Model access" page has been retired. Serverless foundation models now **auto-enable on first invocation** across AWS commercial regions — there is no page to click through. The one catch: for **Anthropic** models, first-time users may have to submit a short use-case form before the first call succeeds.

So clear that gate now, before setup needs it. The fastest way — in the AWS console, go to **Bedrock → Playgrounds → Chat/Text**, pick **Claude 3.5 Sonnet**, send "hello". If a use-case form appears, fill it in (short; usually approved fast). Repeat for **Claude 3.5 Haiku**. Or via CLI:

```bash
aws bedrock-runtime invoke-model \
  --model-id anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --body '{"anthropic_version":"bedrock-2023-08-31","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}' \
  --cli-binary-format raw-in-base64-out /dev/stdout
```

If that returns text, you are clear. If it errors with an access/use-case message, do the console playground route to surface the form. Both Sonnet and Haiku are needed — the router cascades between them.

### 2.3 Create the AgentCore Agent

AgentCore is the AWS equivalent of the Gemini Enterprise Agent Platform — a managed runtime with sandbox isolation.

> **Run § 2.3–2.4 as an admin identity, not the cross-cloud reader.** These steps create IAM roles and AgentCore runtimes. The `mesh-router-cross-cloud` reader user from § 2.5 deliberately has no such permissions, and `AmazonBedrockFullAccess` alone does **not** include `iam:CreateRole`. The clean path: run these from **AWS CloudShell** logged into the console as the account root (or an admin user). CloudShell inherits your console identity, so no key juggling. Do not use the reader user for any creation step — it exists only for the running Mesh service to read with, later.

> **The two commands at the end of this section (build/push the container, create the runtime) are deferred.** They need the `mesh-causal-agent` container image, which does not exist until the codebase is scaffolded and that agent is built (SCAFFOLD.md Milestone 7). Run steps 1–3 below now (the IAM role is harmless and needed); defer the runtime creation.

```bash
# Create the IAM role AgentCore agents run as
aws iam create-role \
    --role-name MeshAgentCoreExecutionRole \
    --assume-role-policy-document file://infra/aws/agentcore_trust_policy.json

aws iam attach-role-policy \
    --role-name MeshAgentCoreExecutionRole \
    --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess

aws iam attach-role-policy \
    --role-name MeshAgentCoreExecutionRole \
    --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess

# Note the role ARN
export AGENTCORE_ROLE_ARN=$(aws iam get-role --role-name MeshAgentCoreExecutionRole --query 'Role.Arn' --output text)

# Create the agent runtime
aws bedrock-agentcore-control create-agent-runtime \
    --agent-runtime-name "mesh-causal-agent" \
    --description "Causal-estimation agent for the AgentLab demo" \
    --execution-role-arn $AGENTCORE_ROLE_ARN \
    --network-configuration "publicNetwork={}" \
    --container-configuration file://infra/aws/agentcore_container.json

# Capture the runtime ARN; we need it later
aws bedrock-agentcore-control list-agent-runtimes
export AGENTCORE_RUNTIME_ARN="arn:aws:bedrock-agentcore:us-east-1:<your-account>:agent-runtime/mesh-causal-agent"
```

> **Pitfall**: If you see "this action is not supported in your region" errors, you're outside `us-east-1`. Re-check `aws configure` defaults.

### 2.4 Set Up Online Evaluation Config

AgentCore has its own online evaluation primitive — exactly the AWS analog of Google's Agent Evaluation API. We configure it here so Mesh has a quality signal to ingest.

```bash
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
```

### 2.5 Create the Cross-Cloud Read Role (for GCP → AWS pulls)

Mesh's AWS adapter (running on GCP Cloud Run) needs to pull from Bedrock + CloudWatch. The cleanest pattern is a long-lived access key for the demo (in production, you'd use AWS IAM Identity Center with OIDC federation from GCP, but that's a 4-hour rabbit hole we skip).

```bash
aws iam create-user --user-name mesh-cross-cloud-reader

aws iam attach-user-policy \
    --user-name mesh-cross-cloud-reader \
    --policy-arn arn:aws:iam::aws:policy/AmazonBedrockReadOnly

aws iam attach-user-policy \
    --user-name mesh-cross-cloud-reader \
    --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsReadOnlyAccess

# Create an access key for this user
aws iam create-access-key --user-name mesh-cross-cloud-reader > aws-key.json

# Store the access key in GCP Secret Manager so the Cloud Run adapter can read it
cat aws-key.json | jq -r '.AccessKey.AccessKeyId' | \
    gcloud secrets create aws-access-key-id --data-file=- --project=$GCP_PROJECT_ID

cat aws-key.json | jq -r '.AccessKey.SecretAccessKey' | \
    gcloud secrets create aws-secret-access-key --data-file=- --project=$GCP_PROJECT_ID

rm aws-key.json  # do not check this into git
```

### 2.6 Register Agent 3 in the Canonical Registry

Back in GCP:

```bash
gcloud agent-platform registry agents register \
    --agent-id=causal-estimation \
    --platform=aws-agentcore \
    --endpoint=$AGENTCORE_RUNTIME_ARN \
    --metadata="mesh.platform=AWS,mesh.task_family=causal_estimation,mesh.step=2,aws.region=us-east-1"
```

### 2.7 Save the AWS Environment File

```bash
cat > .env.aws <<EOF
AWS_REGION=us-east-1
AGENTCORE_RUNTIME_ARN=$AGENTCORE_RUNTIME_ARN
AGENTCORE_ROLE_ARN=$AGENTCORE_ROLE_ARN
EOF
```

**You are done with AWS.** Save your AWS console tab — you'll glance at CloudWatch logs during debugging. Azure is next, and it's shorter.

---

## Part 3 — Microsoft Azure

Azure hosts the Step-3 agent — the experiment readout drafter. It calls **Azure OpenAI (gpt-4o) directly** through a thin self-authored harness. Mesh consumes Azure telemetry via Application Insights and Azure Monitor.

> **Why not Copilot Studio?** The original plan used Copilot Studio. It hard-gates to Microsoft Entra *work/school* accounts and rejects personal accounts outright — so a personal Gmail-based Azure subscription cannot author a Copilot Studio agent. Rather than stand up a whole Entra tenant (hours of detour with no guarantee), the Azure agent calls Azure OpenAI directly. This is still a genuinely real Azure agent: real Azure infrastructure, real gpt-4o, real Application Insights traces. The federation thesis holds completely; only the agent harness is simpler.

> **Security reminder for this entire section.** Never paste an Azure key, connection string, or any other secret into a chat with an AI agent, into a commit, or into a shared doc. Endpoints and resource names are fine — they are addresses, not credentials. Keys go straight into GCP Secret Manager (or a local gitignored `.env`) and nowhere else. If a key is ever exposed, rotate it immediately (Azure Portal → the resource → Keys and Endpoint → Regenerate).

### 3.1 Create the Azure Subscription and Resource Group

Sign up at `azure.microsoft.com/free` if you don't already have a subscription. New accounts get $200 in free credit, valid 30 days. **That credit covers the entire Azure side of this project.**

```bash
az login

# Pick the subscription if you have multiple
az account list --output table
az account set --subscription="<your-subscription-id>"

export AZURE_RG="mesh-router-rg"
export AZURE_REGION="eastus2"   # see § 3.2 pitfall on region/quota

az group create --name $AZURE_RG --location $AZURE_REGION
```

**Register the resource providers up front.** New subscriptions have most providers unregistered, which causes confusing failures later (broken metric charts, telemetry that never appears). Register them now:

```bash
az provider register --namespace Microsoft.CognitiveServices --wait
az provider register --namespace Microsoft.Insights --wait
az provider register --namespace Microsoft.OperationalInsights --wait
```

### 3.2 Provision Azure OpenAI and Deploy gpt-4o

This is the part that fights new subscriptions the hardest. Read the whole section before running anything.

```bash
# Create the Azure OpenAI resource
az cognitiveservices account create \
    --name mesh-openai \
    --resource-group $AZURE_RG \
    --location $AZURE_REGION \
    --kind OpenAI \
    --sku S0 \
    --yes

# Get the endpoint (an address — safe to keep in env)
export AZURE_OPENAI_ENDPOINT=$(az cognitiveservices account show \
    --name mesh-openai --resource-group $AZURE_RG \
    --query "properties.endpoint" -o tsv)

# Get a key and put it STRAIGHT into Secret Manager — do not echo it
az cognitiveservices account keys list \
    --name mesh-openai --resource-group $AZURE_RG \
    --query "key1" -o tsv | \
    gcloud secrets create azure-openai-key --data-file=- --project=$GCP_PROJECT_ID

echo -n "$AZURE_OPENAI_ENDPOINT" | \
    gcloud secrets create azure-openai-endpoint --data-file=- --project=$GCP_PROJECT_ID

# Deploy gpt-4o. Use a CURRENT model version — see pitfalls below.
az cognitiveservices account deployment create \
    --name mesh-openai \
    --resource-group $AZURE_RG \
    --deployment-name "gpt-4o" \
    --model-name "gpt-4o" \
    --model-version "2024-11-20" \
    --model-format OpenAI \
    --sku-name "Standard" \
    --sku-capacity 10
```

> **Pitfall — access approval.** Some new subscriptions require an application before Azure OpenAI resources can be created. If `account create` fails with "operation not allowed", apply at `aka.ms/oai/access`. Approval is usually under 24 hours. File this on Day 0.

> **Pitfall — deprecated model versions.** Model snapshots get retired. If deployment fails with `ServiceModelDeprecated`, the version string is stale. Do not chase a specific old snapshot — list current versions and pick the newest:
> ```bash
> az cognitiveservices model list --location $AZURE_REGION \
>     --query "[?model.name=='gpt-4o'].model.version" -o tsv
> ```
> gpt-4o is better supported than gpt-4o-mini for this purpose; if mini has no live version in your region, just use gpt-4o.

> **Pitfall — quota = 0.** New subscriptions often start with 0 TPM quota for standard chat models. The deploy then fails with `InsufficientQuota`. Three responses, in order: (1) the deployment screen / portal gives a per-model "Request quota" link — submit a small ask (10K TPM); Standard quota requests are often approved within hours. (2) Quota is **per-region** — if `eastus2` is at 0, try `westus3`, `swedencentral`, or `northcentralus`; one usually has headroom. (3) Before requesting, check whether a usable gpt-4o deployment already exists on the subscription from an earlier attempt: `az cognitiveservices account deployment list --name mesh-openai --resource-group $AZURE_RG -o table`.

> **Pitfall — wrong resource.** If you created Azure OpenAI through the Foundry portal as well as the CLI, you may have two resources. Make sure every later step and every `.env.azure` value points at the *one* resource that actually has the working gpt-4o deployment. Mismatched endpoint/region is a silent failure — the adapter calls an empty resource and returns nothing.

**Verify before moving on.** "Deployment exists" and "deployment answers" are different. Open Azure AI Foundry → Playgrounds → Chat, select the gpt-4o deployment, send "hello". A reply confirms the Azure agent's model backend is live. Do not rely on the Metrics tab — it shows chart errors on fresh subscriptions and is not a health check.

### 3.3 Provision Application Insights

Application Insights is where the Azure agent's traces land — the Azure equivalent of Cloud Trace. The Mesh Azure adapter reads from here.

```bash
az monitor app-insights component create \
    --app mesh-insights \
    --location $AZURE_REGION \
    --resource-group $AZURE_RG \
    --application-type web

# Connection string — used to instrument the agent (an address; safe in env)
export AZURE_AI_CONNECTION_STRING=$(az monitor app-insights component show \
    --app mesh-insights --resource-group $AZURE_RG \
    --query "connectionString" -o tsv)

# Read API key for the Mesh adapter — pipe straight into Secret Manager
az monitor app-insights api-key create \
    --app mesh-insights \
    --resource-group $AZURE_RG \
    --api-key mesh-reader \
    --read-properties ReadTelemetry \
    --query "apiKey" -o tsv | \
    gcloud secrets create azure-ai-api-key --data-file=- --project=$GCP_PROJECT_ID

# The App Insights "Application ID" (an identifier — distinct from the resource ID)
export AZURE_AI_APP_ID=$(az monitor app-insights component show \
    --app mesh-insights --resource-group $AZURE_RG \
    --query "appId" -o tsv)
```

> If `Microsoft.Insights` was not registered in § 3.1, the create call fails with "subscription not registered". Run `az provider register --namespace Microsoft.Insights --wait` and retry.

### 3.4 The Readout Agent

There is no Copilot Studio agent to provision. The readout agent — Step 3, which drafts the stakeholder ship/no-ship memo — is plain code. It lives in `agents/readout/` in the codebase and calls Azure OpenAI directly via the `openai` SDK pointed at your Azure endpoint. It is built as part of SCAFFOLD.md Milestone 1 (and gets its real, non-mock implementation by Milestone 7).

There is nothing to click here. The only Azure-side prerequisites are the resource and deployment from § 3.2 and the telemetry from § 3.3, both already done. The agent instruments itself to Application Insights using `AZURE_AI_CONNECTION_STRING`.

A minimal sanity check that the agent's code path works (run once the codebase exists):

```bash
# from the repo root, with .env.azure populated
python -m agents.readout.smoke   # sends one readout-drafting request to Azure gpt-4o
```

### 3.5 Register the Readout Agent in the Canonical Registry

Back in GCP:

```bash
gcloud agent-platform registry agents register \
    --agent-id=readout \
    --platform=azure-openai \
    --endpoint="$AZURE_OPENAI_ENDPOINT" \
    --metadata="mesh.platform=Azure,mesh.task_family=readout,mesh.step=3,azure.app_insights_id=$AZURE_AI_APP_ID,azure.deployment=gpt-4o"
```

### 3.6 Save the Azure Environment File

```bash
cat > .env.azure <<EOF
AZURE_RG=$AZURE_RG
AZURE_REGION=$AZURE_REGION
AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_AI_APP_ID=$AZURE_AI_APP_ID
AZURE_AI_CONNECTION_STRING=$AZURE_AI_CONNECTION_STRING
EOF
```

Keys are intentionally absent from this file — they live in GCP Secret Manager (`azure-openai-key`, `azure-ai-api-key`) and the Mesh services read them from there at runtime.

**You are done with all three clouds.** Now the integration work.

---

## Part 4 — Deploy the AgentLab Services and Console

### 4.1 Build and Deploy the Router

The router runs on Cloud Run. It needs network access to GCP, AWS, and Azure.

```bash
cd router
gcloud builds submit --tag gcr.io/$GCP_PROJECT_ID/agentlab-router

gcloud run deploy mesh-router \
    --image gcr.io/$GCP_PROJECT_ID/agentlab-router \
    --region=$GCP_REGION \
    --service-account=$SA_EMAIL \
    --allow-unauthenticated \
    --port=8080 \
    --memory=2Gi \
    --set-secrets="AWS_ACCESS_KEY_ID=aws-access-key-id:latest,AWS_SECRET_ACCESS_KEY=aws-secret-access-key:latest,AZURE_AI_API_KEY=azure-ai-api-key:latest,SLACK_BOT_TOKEN=slack-bot-token:latest" \
    --set-env-vars="GCP_PROJECT_ID=$GCP_PROJECT_ID,AWS_REGION=us-east-1,AZURE_AI_APP_ID=$AZURE_AI_APP_ID" \
    --project=$GCP_PROJECT_ID

export MESH_ROUTER_URL=$(gcloud run services describe mesh-router \
    --region=$GCP_REGION --format="value(status.url)" --project=$GCP_PROJECT_ID)
```

### 4.2 Build and Deploy the Triage Agent

The triage agent is a separate Cloud Run service (it has a different scaling profile — bursty every 15 minutes vs the router which is always-on).

```bash
cd triage
gcloud builds submit --tag gcr.io/$GCP_PROJECT_ID/agentlab-triage

gcloud run deploy mesh-triage \
    --image gcr.io/$GCP_PROJECT_ID/agentlab-triage \
    --region=$GCP_REGION \
    --service-account=$SA_EMAIL \
    --no-allow-unauthenticated \
    --memory=4Gi \
    --project=$GCP_PROJECT_ID

# Schedule it to run every 15 minutes
gcloud scheduler jobs create http mesh-triage-schedule \
    --schedule="*/15 * * * *" \
    --uri="$(gcloud run services describe mesh-triage --region=$GCP_REGION --format='value(status.url)' --project=$GCP_PROJECT_ID)/run" \
    --http-method=POST \
    --oidc-service-account-email=$SA_EMAIL \
    --location=$GCP_REGION \
    --project=$GCP_PROJECT_ID
```

### 4.3 Deploy the Console (Mesh UI)

The visual demo. Next.js + Tailwind + shadcn/ui on Cloud Run.

```bash
cd console
pnpm install
pnpm build

# Containerize
gcloud builds submit --tag gcr.io/$GCP_PROJECT_ID/agentlab-console

gcloud run deploy mesh-console \
    --image gcr.io/$GCP_PROJECT_ID/agentlab-console \
    --region=$GCP_REGION \
    --service-account=$SA_EMAIL \
    --allow-unauthenticated \
    --port=3000 \
    --memory=1Gi \
    --set-env-vars="MESH_ROUTER_URL=$MESH_ROUTER_URL,NEXT_PUBLIC_GCP_PROJECT=$GCP_PROJECT_ID" \
    --project=$GCP_PROJECT_ID

export MESH_CONSOLE_URL=$(gcloud run services describe mesh-console \
    --region=$GCP_REGION --format="value(status.url)" --project=$GCP_PROJECT_ID)

echo "Console: $MESH_CONSOLE_URL"
```

Open the console URL in a browser. You should see the Pipeline view populated with the workflow agents across three clouds. If you only see GCP agents, the AWS / Azure adapters haven't pulled yet — see [Troubleshooting](#troubleshooting).

### 4.4 Wire the Slack App's Request URLs

Now that the router is deployed and has a real URL, update the Slack app:

1. `api.slack.com/apps` → your AgentLab Slack app
2. Interactivity & Shortcuts → Request URL → `$MESH_ROUTER_URL/slack/interactive`
3. Slash Commands → `/mesh` → Request URL → `$MESH_ROUTER_URL/slack/commands`
4. Save

Test it: in your demo Slack workspace, type `/mesh status` → you should see a card showing the registered agents.

---

## Cost Notes

Approximate costs during the hackathon window (May 14 – May 25), on the **cheap-cloud path** (BigQuery vector search, classifiers co-hosted, free GCP/Azure credits). Order of magnitude, not exact:

| Cloud  | Resource                                    | Approx Cost   | Notes                                                    |
|--------|---------------------------------------------|---------------|----------------------------------------------------------|
| GCP    | Cloud Run (router + triage + console)       | $5            | Mostly idle; scales to zero. Co-hosts the classifiers.   |
| GCP    | Gemini API calls (3.5 Flash)                | $20           | Demo traffic is small                                    |
| GCP    | BigQuery (incl. vector search) + Trace + Pub/Sub | $5       | Mostly free-tier; demo data is tiny                      |
| GCP    | Vector search                               | $0            | BigQuery `VECTOR_SEARCH` — no standing cost              |
| GCP    | Classifier hosting                          | $0            | DistilBERT co-hosted in the router container             |
| AWS    | Bedrock Claude 3.5 Sonnet calls             | $25           | ~$3 per 1M input tokens; demo traffic small              |
| AWS    | AgentCore Runtime (idle + active)           | $20           | Pricing is per-runtime-hour                              |
| AWS    | CloudWatch logs + storage                   | $3            |                                                          |
| Azure  | Azure OpenAI (GPT-4o)                       | $15           | $200 free credit covers all of this                      |
| Azure  | Application Insights                        | $0            | First 5 GB/month free                                    |
| Azure  | (no Copilot Studio — agent calls Azure OpenAI directly) | $0   | Dropped; Copilot Studio needs an Entra work account     |
| Slack  | Slack workspace                             | $0            | Free                                                     |
| **TOTAL (cheap path)** | (post hackathon)               | **~$95**      | And GCP's $300 free credit covers the GCP rows           |
| *Optional* | AlloyDB AI swap (if you take it)         | +$90          | Only if you want sub-50ms latency in the demo            |


The Azure $200 free credit pays for the whole Azure side and GCP's $300 free credit covers the GCP rows, so on the cheap path your real out-of-pocket is roughly the AWS spend alone — about **$45–50**. Total economic cost (ignoring free credits) is ~$95.

---

## Troubleshooting

### "I see only GCP agents in the Pipeline view"

The AWS or Azure adapters in the Mesh router service haven't successfully pulled yet. Check:

```bash
gcloud run services logs read mesh-router --region=$GCP_REGION --limit=50 \
    --project=$GCP_PROJECT_ID | grep -E "(aws|azure)" -i
```

Common causes:
- AWS access key invalid → re-run § 2.5
- AWS region wrong → router env must say `AWS_REGION=us-east-1`
- Azure App Insights API key missing → re-run § 3.3
- Azure App ID wrong → re-check § 3.4 final step

### "BigQuery vector search is slow or erroring"

Make sure the embedding column is the right dimension (`gemini-embedding-001` returns 768 or 1536 depending on the output config you chose — keep it consistent) and that you created a vector index on the table:

```sql
CREATE VECTOR INDEX agent_capability_idx
    ON `PROJECT.mesh.agent_capabilities`(embedding)
    OPTIONS(index_type = 'IVF', distance_type = 'COSINE');
```

For a handful of agents the index is optional — a brute-force `VECTOR_SEARCH` over a handful of rows is instant. The index matters only if you scale the fleet.

*(If you took the optional AlloyDB swap instead: connect via AlloyDB Studio and run `CREATE EXTENSION IF NOT EXISTS vector;` then an `ivfflat` index on the embedding column.)*

### "Bedrock model access denied"

Did you opt in to Claude 3.5 Sonnet *and* Haiku in § 2.2? Both are needed; the router cascades between them.

### "Gemini API rate limited"

If you're on the free Gemini API tier, you'll hit rate limits during demo dry-runs. Upgrade your project to the paid tier on the Gemini API console.

### "Cloud Run service takes >30s to wake up"

Cloud Run scales to zero between requests. For the demo, set `--min-instances=1` on the router and console to keep one warm instance.

```bash
gcloud run services update mesh-router --min-instances=1 --region=$GCP_REGION --project=$GCP_PROJECT_ID
gcloud run services update mesh-console --min-instances=1 --region=$GCP_REGION --project=$GCP_PROJECT_ID
```

This adds about $2/day per service but eliminates demo-day stage fright.

---

## Post-Hackathon Cleanup Checklist

After your demo, run through this to stop the bleeding:

```bash
# GCP — scale Cloud Run back to zero
gcloud run services update mesh-router --min-instances=0 --region=$GCP_REGION --project=$GCP_PROJECT_ID
gcloud run services update mesh-console --min-instances=0 --region=$GCP_REGION --project=$GCP_PROJECT_ID

# GCP — ONLY if you took the optional AlloyDB swap
# gcloud alloydb instances delete mesh-primary --cluster=mesh-cluster --region=$GCP_REGION --project=$GCP_PROJECT_ID --quiet
# gcloud alloydb clusters delete mesh-cluster --region=$GCP_REGION --project=$GCP_PROJECT_ID --quiet

# (No Vertex AI endpoints to delete — classifiers are co-hosted in the router container)

# AWS — delete the AgentCore runtime
aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-name "mesh-causal-agent"
aws bedrock-agentcore-control delete-online-evaluation-config --online-evaluation-config-name "mesh-causal-eval"

# Azure — easiest is to delete the resource group
az group delete --name $AZURE_RG --yes --no-wait
```

If you want to keep the project as a portfolio piece (recommended for the recruiter conversations after the hackathon), keep the **GCP project + console + router** alive — on the cheap path that costs roughly **$2–3/day** with Cloud Run scaled low, which is fine to leave running for weeks. Delete the **AWS AgentCore runtime and Azure resource group** since those don't scale to zero.

---

## Suggested Setup Sequence

This guide is the *infrastructure* setup. It pairs with [`SCAFFOLD.md`](SCAFFOLD.md) (the codebase build order) and [`VALIDATION.md`](VALIDATION.md) (the end-to-end checks). A sane sequence:

1. **Bootstrap accounts and access** — GCP project + billing, AWS account, Azure subscription, and any access requests that have approval delays (Azure OpenAI access form especially). Do the slow-approval items first.
2. **GCP — Part 1.** The longest section; the canonical cloud. Stand up the project, APIs, service account, BigQuery, Pub/Sub, the Slack app.
3. **AWS — Part 2** up to the points marked *deferred*. The IAM role and reader user can be created now; the AgentCore runtime and online-eval config wait for the agent container.
4. **Azure — Part 3.** Resource, gpt-4o deployment, Application Insights. Verify gpt-4o answers in the Foundry Chat playground.
5. **Scaffold and build the codebase** via SCAFFOLD.md Milestones 0–6 (MOCK mode — no cloud needed).
6. **Milestone 7** — build the agent containers, flip `MOCK=false`, and run the deferred steps: AWS § 2.3 final command, § 2.4, § 2.6.
7. **Part 4** — deploy the AgentLab services and the console.
8. **Validate** end to end with [`VALIDATION.md`](VALIDATION.md).

If something is broken when it matters, [`FALLBACK.md`](FALLBACK.md) has the collapse plan.

---

## Final Note on Cloud Choice

Using all three clouds for real is a deliberate choice. It costs roughly 4–6 hours of setup and about $95 economically — with GCP and Azure free credits, only ~$45–50 of real out-of-pocket spend.

But remember the project's actual headline: **fault localization** — the system pinning a pipeline's quality regression to the step that actually caused it, separating cause from downstream symptom, then closing the loop to repair it. Cross-cloud is a *setting that makes the failure realistic*, not the centerpiece. Build the three clouds because a real cross-cloud trace is impressive and substantial; but the minutes that win the demo are the triage agent visibly localizing the fault and the pipeline recovering, not the architecture diagram. Keep that proportion right — in the build effort and in the demo.

Good luck. Ship it.
