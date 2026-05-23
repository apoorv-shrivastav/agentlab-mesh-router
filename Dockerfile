# 1. Base image with Node and Python
FROM node:20-slim

# Install Python 3, venv, make, and build essentials
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    make \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Copy the Python packages and code files first to allow pip install to succeed
COPY pyproject.toml README.md ./
COPY common ./common
COPY mesh ./mesh
COPY router ./router
COPY signals ./signals
COPY triage ./triage
COPY sentry ./sentry
COPY orchestrator ./orchestrator
COPY agents ./agents

# Build the virtualenv and install python dependencies
RUN python3 -m venv .venv && \
    .venv/bin/pip install --no-cache-dir .

# 3. Copy the rest of the application files (e.g. scripts, harness, agentlab.db)
COPY . .

# 4. Install Node dependencies and build the Next.js console
WORKDIR /app/console
RUN npm install -g pnpm && \
    pnpm install --ignore-scripts && \
    pnpm run build

# Expose the Next.js default port
EXPOSE 3000

# Start Next.js server
CMD ["pnpm", "start"]
