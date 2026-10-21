"""FastAPI game API for The Lyceum."""

from __future__ import annotations

import uuid
import hashlib
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .agents import AgentCallError, evaluate, philosopher_turn, visible_reply
except ImportError:  # uvicorn main:app from inside backend/
    from agents import AgentCallError, evaluate, philosopher_turn, visible_reply
from harness import Budget, looks_like_prompt_injection, validate_player_message
from tools import GameState, audit_event

app = FastAPI(title="The Lyceum API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)
AUDIT_PATH = Path(__file__).resolve().parents[1] / "output" / "audit.jsonl"
SESSIONS: dict[str, GameState] = {}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


def public_state(state: GameState) -> dict:
    return {
        **state.model_dump(),
        "philosopher": state.philosopher,
        "complete": state.complete,
    }


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": "lyceumv4"}


@app.post("/api/sessions")
async def create_session() -> dict:
    session_id = uuid.uuid4().hex
    state = GameState(session_id=session_id)
    budget = Budget()
    try:
        greeting, _ = await philosopher_turn(
            state,
            "A visitor has just entered the room. Greet them naturally, as yourself.",
            budget,
        )
    except AgentCallError as exc:
        audit_event(AUDIT_PATH, "philosopher_model_error", session_id=session_id, philosopher=state.philosopher)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    state.messages.append({"role": "assistant", "content": visible_reply(greeting)})
    state.budget_requests = budget.requests
    state.budget_output_tokens = budget.output_tokens
    SESSIONS[session_id] = state
    audit_event(AUDIT_PATH, "session_started", session_id=session_id, philosopher="plato")
    return public_state(state)


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    state = SESSIONS.get(session_id)
    if not state:
        raise HTTPException(404, "Session not found")
    return public_state(state)


@app.post("/api/sessions/{session_id}/messages")
async def send_message(session_id: str, request: ChatRequest) -> dict:
    state = SESSIONS.get(session_id)
    if not state:
        raise HTTPException(404, "Session not found")
    if state.complete:
        raise HTTPException(409, "The Lyceum has been completed.")
    message = validate_player_message(request.message)
    injection_attempt = looks_like_prompt_injection(message)
    if injection_attempt:
        audit_event(AUDIT_PATH, "injection_blocked", session_id=session_id, philosopher=state.philosopher)
        raise HTTPException(
            status_code=400,
            detail="Instruction override requests are blocked. Continue with a question or philosophical argument.",
        )
    budget = Budget(requests=state.budget_requests, output_tokens=state.budget_output_tokens)
    try:
        reply, _ = await philosopher_turn(state, message, budget)
    except AgentCallError as exc:
        state.budget_requests = budget.requests
        state.budget_output_tokens = budget.output_tokens
        audit_event(AUDIT_PATH, "philosopher_model_error", session_id=session_id, philosopher=state.philosopher)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    result = await evaluate(state, message, reply, budget)
    display_reply = visible_reply(reply)
    state.messages.extend([{"role": "user", "content": message}, {"role": "assistant", "content": display_reply}])
    state.budget_requests = budget.requests
    state.budget_output_tokens = budget.output_tokens
    advanced = False
    belief = None
    philosopher = state.philosopher
    state.conviction.setdefault(philosopher, 100)
    # Exact repeated submissions cannot farm conviction loss. The evaluator
    # remains the sole authority for both progress classification and victory.
    fingerprint = hashlib.sha256(f"{philosopher}: {re.sub(r"\s+", " ", message.strip().lower())}".encode("utf-8")).hexdigest()
    progress_level = str(result.get("progress_level", "none"))
    if progress_level in {"minor", "substantial"} and fingerprint not in state.progress_fingerprints:
        state.progress_fingerprints.append(fingerprint)
        deduction = 8 if progress_level == "minor" else 20
        state.conviction[philosopher] = max(10, state.conviction[philosopher] - deduction)
    if result.get("persuaded") and philosopher not in state.persuaded:
        belief = str(result.get("belief") or "a stated commitment")[:200]
        state.persuaded.append(philosopher)
        state.conviction[philosopher] = 0
        state.philosopher_index += 1
        advanced = True
    audit_event(
        AUDIT_PATH,
        "turn_completed",
        session_id=session_id,
        philosopher=state.philosopher,
        advanced=advanced,
        requests=budget.requests,
    )
    return {"reply": display_reply, "evaluation": result, "advanced": advanced, "belief": belief, "state": public_state(state)}
