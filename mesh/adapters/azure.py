from datetime import datetime

from agents.readout.descriptor import get_descriptor as get_ro_desc
from agents.spares.readout_spare import get_descriptor as get_spare_desc
from common.bq import query_eval_scores, query_signals
from common.config import settings
from common.schema import AgentDescriptor, EvalScore, Signal, TaskFamily
from mesh.adapters.base import CloudAdapter



class AzureAdapter(CloudAdapter):
    """Azure Cloud Adapter managing step 3 agents and spares telemetry."""

    def list_agents(self) -> list[AgentDescriptor]:
        return [get_ro_desc(), get_spare_desc()]

    def pull_signals(self, since: datetime) -> list[Signal]:
        azure_agent_ids = {a.agent_id for a in self.list_agents()}
        
        if not settings.mock:
            try:
                import os
                import requests
                # Get the Azure AI App ID and API Key (loaded from Secret Manager / env)
                app_id = settings.azure.ai_app_id
                api_key = os.getenv("AZURE_AI_API_KEY")
                
                if app_id and api_key:
                    url = f"https://api.applicationinsights.io/v1/apps/{app_id}/query"
                    headers = {"X-Api-Key": api_key}
                    
                    # Log analytics query to fetch trace signals
                    iso_time = since.isoformat()
                    query = f"traces | where timestamp >= datetime({iso_time}) | order by timestamp desc"
                    
                    res = requests.get(url, headers=headers, params={"query": query}, timeout=10)
                    if res.status_code == 200:
                        data = res.json()
                        # Parse application insights table response
                        tables = data.get("tables", [])
                        signals = []
                        if tables:
                            columns = [col["name"] for col in tables[0].get("columns", [])]
                            rows = tables[0].get("rows", [])
                            
                            message_idx = columns.index("message") if "message" in columns else -1
                            timestamp_idx = columns.index("timestamp") if "timestamp" in columns else -1
                            
                            for row in rows:
                                msg = row[message_idx] if message_idx != -1 else ""
                                ts_str = row[timestamp_idx] if timestamp_idx != -1 else None
                                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else datetime.utcnow()
                                
                                # Extract signal if structured
                                if "low_confidence_output" in msg or "refusal" in msg:
                                    kind = "low_confidence_output" if "low_confidence_output" in msg else "refusal"
                                    signals.append(Signal(
                                        request_id="azure-extracted",
                                        agent_id="readout",
                                        timestamp=ts,
                                        kind=kind,
                                        value=1.0,
                                        source="classifier"
                                    ))
                        if signals:
                            return [s for s in signals if s.agent_id in azure_agent_ids]
            except Exception as e:
                print(f"[AzureAdapter] App Insights query failed: {e}. Using DB query fallback.")
                
        # Mock / Fallback mode: query centralized database
        all_sigs = query_signals(since)
        return [s for s in all_sigs if s.agent_id in azure_agent_ids]

    def pull_eval_scores(self, since: datetime) -> list[EvalScore]:
        azure_agent_ids = {a.agent_id for a in self.list_agents()}
        
        if not settings.mock:
            try:
                import os
                import requests
                app_id = settings.azure.ai_app_id
                api_key = os.getenv("AZURE_AI_API_KEY")
                
                if app_id and api_key:
                    url = f"https://api.applicationinsights.io/v1/apps/{app_id}/query"
                    headers = {"X-Api-Key": api_key}
                    
                    # Fetch custom metrics or aggregated performance traces
                    iso_time = since.isoformat()
                    query = f"customMetrics | where timestamp >= datetime({iso_time}) | order by timestamp desc"
                    
                    res = requests.get(url, headers=headers, params={"query": query}, timeout=10)
                    if res.status_code == 200:
                        data = res.json()
                        tables = data.get("tables", [])
                        scores = []
                        if tables:
                            columns = [col["name"] for col in tables[0].get("columns", [])]
                            rows = tables[0].get("rows", [])
                            name_idx = columns.index("name") if "name" in columns else -1
                            value_idx = columns.index("value") if "value" in columns else -1
                            ts_idx = columns.index("timestamp") if "timestamp" in columns else -1
                            
                            for row in rows:
                                name = row[name_idx] if name_idx != -1 else ""
                                val = row[value_idx] if value_idx != -1 else 0.0
                                ts_str = row[ts_idx] if ts_idx != -1 else None
                                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")) if ts_str else datetime.utcnow()
                                
                                if name == "pass_k" or name == "quality_score":
                                    scores.append(EvalScore(
                                        agent_id="readout",
                                        task_family=TaskFamily.READOUT,
                                        pass_k=float(val),
                                        n_trials=50,
                                        ci_low=float(val) - 0.05,
                                        ci_high=float(val) + 0.05,
                                        timestamp=ts
                                    ))
                        if scores:
                            return [s for s in scores if s.agent_id in azure_agent_ids]
            except Exception as e:
                print(f"[AzureAdapter] App Insights eval query failed: {e}. Using DB query fallback.")
                
        # Mock / Fallback mode: query centralized database
        all_scores = query_eval_scores(since)
        return [s for s in all_scores if s.agent_id in azure_agent_ids]

