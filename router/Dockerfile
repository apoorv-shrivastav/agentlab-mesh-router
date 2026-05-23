FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Pre-install working versions of boto3, botocore, aiobotocore, aioboto3, and inspect-ai to prevent pip backtracking on botocore conflicts
RUN pip install --no-cache-dir \
    botocore==1.40.61 \
    boto3==1.40.61 \
    aiobotocore==2.25.1 \
    aioboto3==15.5.0 \
    inspect-ai==0.3.224

COPY pyproject.toml README.md ./
COPY common ./common
COPY mesh ./mesh
COPY router ./router
COPY signals ./signals
COPY triage ./triage
COPY sentry ./sentry
COPY orchestrator ./orchestrator
COPY agents ./agents
COPY harness ./harness

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["uvicorn", "router.server:app", "--host", "0.0.0.0", "--port", "8080"]
