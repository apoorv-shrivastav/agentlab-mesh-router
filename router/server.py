import asyncio
import json
import urllib.parse
import uuid
from typing import Set

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from common.bq import write_route_decision
from common.schema import RouteDecision, TaskFamily
from mesh.registry import list_all_agents
from router.bandit import route_bandit
from router.baseline_embed_match import route_baseline
from router.cascade import route_cascade
from router.learned_router import LearnedRouter

app = FastAPI(title="AgentLab Router Server", version="1.0.0")

# SSE Decision Broker
class DecisionBroker:
    def __init__(self):
        self.subscribers: Set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self.subscribers.discard(q)

    def publish(self, decision: RouteDecision):
        for q in self.subscribers:
            q.put_nowait(decision)

broker = DecisionBroker()

class RouteRequest(BaseModel):
    request_id: str | None = None
    prompt: str
    task_family: TaskFamily | None = None
    router_kind: str = "baseline"  # "baseline" | "learned" | "bandit" | "cascade"
    cost_weight: float = 0.5
    lambda_val: float = 0.5
    alpha: float = 1.5
    confidence_threshold: float = 0.85

def infer_task_family(prompt: str) -> TaskFamily:
    p_lower = prompt.lower()
    if any(k in p_lower for k in ["prep", "srm", "randomization", "data"]):
        return TaskFamily.DATA_PREP
    elif any(k in p_lower for k in ["causal", "estimation", "cuped", "lift", "effect"]):
        return TaskFamily.CAUSAL_ESTIMATION
    elif any(k in p_lower for k in ["readout", "memo", "stakeholder", "recommendation"]):
        return TaskFamily.READOUT
    # Default fallback
    return TaskFamily.DATA_PREP

@app.post("/route", response_model=RouteDecision)
async def route_request(payload: RouteRequest):
    req_id = payload.request_id or str(uuid.uuid4())

    # Infer task family if not provided
    tf = payload.task_family
    if tf is None:
        tf = infer_task_family(payload.prompt)

    candidates = list_all_agents()

    try:
        if payload.router_kind == "baseline":
            decision = route_baseline(
                request_id=req_id,
                prompt=payload.prompt,
                task_family=tf,
                candidates=candidates,
                cost_weight=payload.cost_weight
            )
        elif payload.router_kind == "learned":
            learned_router = LearnedRouter()
            decision = learned_router.route(
                request_id=req_id,
                prompt=payload.prompt,
                task_family=tf,
                candidates=candidates,
                lambda_val=payload.lambda_val
            )
        elif payload.router_kind == "bandit":
            decision = route_bandit(
                request_id=req_id,
                prompt=payload.prompt,
                task_family=tf,
                candidates=candidates,
                alpha=payload.alpha
            )
        elif payload.router_kind == "cascade":
            decision = route_cascade(
                request_id=req_id,
                prompt=payload.prompt,
                task_family=tf,
                candidates=candidates,
                confidence_threshold=payload.confidence_threshold
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown router kind: {payload.router_kind}"
            )

        # Log decision to SQLite/BigQuery
        write_route_decision(decision)

        # Publish decision to SSE subscribers
        broker.publish(decision)

        return decision

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing error: {str(e)}")

@app.get("/stream")
async def stream_decisions():
    """Server-Sent Events endpoint streaming route decisions in real-time."""
    q = broker.subscribe()
    async def event_generator():
        yield "data: {\"event\": \"connected\"}\n\n"
        try:
            while True:
                decision = await q.get()
                yield f"data: {decision.model_dump_json()}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            broker.unsubscribe(q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/train")
def train_router():
    """Explicitly triggers training of the LightGBM learned model."""
    learned_router = LearnedRouter()
    success = learned_router.train()
    if success:
        return {"status": "success", "message": "Model trained and saved."}
    else:
        return {
            "status": "ignored",
            "message": "Training skipped or failed (insufficient historical data)."
        }

# Slack Integration Placeholders


@app.post("/slack/interactive")
async def slack_interactive(request: Request):
    """Placeholder endpoint for Slack interactive component payloads."""
    body = await request.body()
    params = urllib.parse.parse_qs(body.decode("utf-8"))
    payload = params.get("payload", [None])[0]
    if payload:
        try:
            data = json.loads(payload)
            print(f"[Slack Interactive] Received interaction: {data.get('type')}")
        except Exception:
            pass
    return {"status": "ok"}

@app.post("/slack/commands")
async def slack_commands(request: Request):
    """Placeholder endpoint for Slack slash commands."""
    body = await request.body()
    params = urllib.parse.parse_qs(body.decode("utf-8"))
    command = params.get("command", [None])[0]
    text = params.get("text", [None])[0]
    print(f"[Slack Slash Command] Received command: {command} with text: {text}")
    return {
        "response_type": "ephemeral",
        "text": f"AgentLab Router received slash command {command}. Processing routing request..."
    }
