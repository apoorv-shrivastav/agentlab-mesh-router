import json
from datetime import datetime

from agents.causal_estimation.descriptor import get_descriptor as get_ce_desc
from agents.spares.causal_spare import get_descriptor as get_spare_desc
from common.bq import query_eval_scores, query_signals
from common.config import settings
from common.schema import AgentDescriptor, EvalScore, Signal, TaskFamily
from mesh.adapters.base import CloudAdapter



class AWSAdapter(CloudAdapter):
    """AWS Cloud Adapter managing step 2 agents and spares telemetry."""

    def list_agents(self) -> list[AgentDescriptor]:
        return [get_ce_desc(), get_spare_desc()]

    def pull_signals(self, since: datetime) -> list[Signal]:
        aws_agent_ids = {a.agent_id for a in self.list_agents()}
        
        if not settings.mock:
            try:
                import boto3
                logs_client = boto3.client('logs', region_name=settings.aws.region)
                # Query CloudWatch logs representing agent signal telemetry
                log_group_name = "/aws/bedrock/agent-runtimes/mesh-causal-agent"
                
                # Convert datetime since to milliseconds timestamp
                start_time_ms = int(since.timestamp() * 1000)
                
                response = logs_client.filter_log_events(
                    logGroupName=log_group_name,
                    startTime=start_time_ms,
                    limit=100
                )
                
                signals = []
                for event in response.get("events", []):
                    message = event.get("message", "")
                    try:
                        # Attempt to parse signal from log line if JSON structured
                        data = json.loads(message)
                        if "kind" in data and "request_id" in data:
                            signals.append(Signal(
                                request_id=data["request_id"],
                                agent_id=data.get("agent_id", "causal-estimation"),
                                timestamp=datetime.fromtimestamp(event["timestamp"] / 1000.0),
                                kind=data["kind"],
                                value=float(data.get("value", 1.0)),
                                source=data.get("source", "classifier")
                            ))
                    except Exception:
                        # Non-structured log line, check for keywords
                        if "out_of_bounds" in message:
                            signals.append(Signal(
                                request_id="cw-extracted",
                                agent_id="causal-estimation",
                                timestamp=datetime.fromtimestamp(event["timestamp"] / 1000.0),
                                kind="out_of_bounds",
                                value=1.0,
                                source="explicit"
                            ))
                            
                if signals:
                    return [s for s in signals if s.agent_id in aws_agent_ids]
            except Exception as e:
                print(f"[AWSAdapter] Boto3 CloudWatch logs query failed: {e}. Using DB query fallback.")
        
        # Mock / Fallback mode: query centralized database
        all_sigs = query_signals(since)
        return [s for s in all_sigs if s.agent_id in aws_agent_ids]

    def pull_eval_scores(self, since: datetime) -> list[EvalScore]:
        aws_agent_ids = {a.agent_id for a in self.list_agents()}
        
        if not settings.mock:
            try:
                import boto3
                # Query Bedrock online evaluation config and fetch evaluations
                bedrock_client = boto3.client('bedrock-agent', region_name=settings.aws.region)
                # Retrieve evaluation metrics from the Bedrock online evaluation service
                # (represented by the mesh-causal-eval setup)
                # VERIFY: In standard Bedrock, online evaluation logs are exported to CloudWatch Logs
                logs_client = boto3.client('logs', region_name=settings.aws.region)
                log_group_name = "/aws/bedrock/agent-eval/mesh-causal-eval"
                
                response = logs_client.filter_log_events(
                    logGroupName=log_group_name,
                    startTime=int(since.timestamp() * 1000),
                    limit=50
                )
                
                scores = []
                for event in response.get("events", []):
                    try:
                        data = json.loads(event["message"])
                        # Parse pass_k from Bedrock Agent Evaluation built-in metrics
                        if "metrics" in data:
                            scores.append(EvalScore(
                                agent_id="causal-estimation",
                                task_family=TaskFamily.CAUSAL_ESTIMATION,
                                pass_k=float(data["metrics"].get("pass_rate", 0.95)),
                                n_trials=int(data["metrics"].get("total_cases", 100)),
                                ci_low=float(data["metrics"].get("ci_low", 0.90)),
                                ci_high=float(data["metrics"].get("ci_high", 0.99)),
                                timestamp=datetime.fromtimestamp(event["timestamp"] / 1000.0)
                            ))
                    except Exception:
                        pass
                if scores:
                    return [s for s in scores if s.agent_id in aws_agent_ids]
            except Exception as e:
                print(f"[AWSAdapter] Boto3 Bedrock evaluation query failed: {e}. Using DB query fallback.")
                
        # Mock / Fallback mode: query centralized database
        all_scores = query_eval_scores(since)
        return [s for s in all_scores if s.agent_id in aws_agent_ids]

