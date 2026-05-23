import os
from pathlib import Path

from pydantic_settings import BaseSettings


# We manually locate and load the different env files since there are multiple.
# This ensures that standard dotenv behavior works even if run from different subdirectories.
def load_all_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        # Fallback manual env file parser if python-dotenv isn't installed yet
        def manual_load(path: Path):
            if not path.is_file():
                return
            with open(path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key, val = parts[0].strip(), parts[1].strip()
                        if key not in os.environ:
                            os.environ[key] = val

        root = Path(__file__).resolve().parent.parent
        manual_load(root / ".env")
        manual_load(root / ".env.gcp")
        manual_load(root / ".env.aws")
        manual_load(root / ".env.azure")
        return

    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")
    load_dotenv(root / ".env.gcp")
    load_dotenv(root / ".env.aws")
    load_dotenv(root / ".env.azure")

load_all_env()

class GCPConfig(BaseSettings):
    project_id: str | None = os.getenv("GCP_PROJECT_ID")
    region: str = os.getenv("GCP_REGION", "us-central1")
    sa_email: str | None = os.getenv("SA_EMAIL")
    vector_backend: str = os.getenv("VECTOR_BACKEND", "bigquery")
    dataset_signals: str = os.getenv("BIGQUERY_DATASET_SIGNALS", "mesh")
    dataset_evals: str = os.getenv("BIGQUERY_DATASET_EVALS", "evals")

class AWSConfig(BaseSettings):
    region: str = os.getenv("AWS_REGION", "us-east-1")
    agentcore_runtime_arn: str | None = os.getenv("AGENTCORE_RUNTIME_ARN")
    agentcore_role_arn: str | None = os.getenv("AGENTCORE_ROLE_ARN")

class AzureConfig(BaseSettings):
    rg: str = os.getenv("AZURE_RG", "mesh-router-rg")
    region: str = os.getenv("AZURE_REGION", "eastus2")
    openai_endpoint: str | None = os.getenv("AZURE_OPENAI_ENDPOINT")
    openai_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    ai_app_id: str | None = os.getenv("AZURE_AI_APP_ID")
    ai_connection_string: str | None = os.getenv("AZURE_AI_CONNECTION_STRING")

class Settings(BaseSettings):
    mock: bool = os.getenv("MOCK", "true").lower() in ("true", "1", "yes")
    gcp: GCPConfig = GCPConfig()
    aws: AWSConfig = AWSConfig()
    azure: AzureConfig = AzureConfig()

settings = Settings()
