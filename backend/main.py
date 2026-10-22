"""FastAPI game API for The Lyceum."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .agents import AgentCallError, evaluate, philosopher_turn, visible_reply
except ImportError:  # uvicorn main:app from inside backend/
    from agents import AgentCallError, evaluate, philosopher_turn, visible_reply
from harness import Budget, looks_like_prompt_injection, validate_player_message
from tools import GameState, PHILOSOPHERS, audit_event

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


def session_opening_prompt() -> str:
    return "A visitor has just entered the room. Greet them naturally, as yourself."


async def open_session(state: GameState) -> None:
    budget = Budget()
    try:
        greeting, _ = await philosopher_turn(state, session_opening_prompt(), budget)
    except AgentCallError:
        raise
    state.messages.append({"role": "assistant", "content": visible_reply(greeting)})
    state.budget_requests = budget.requests
    state.budget_output_tokens = budget.output_tokens


def is_explicit_surrender(message: str) -> bool:
    """Recognize only direct first-person admissions of defeat."""
    text = " ".join(message.lower().strip().split())
    if not text or any(word in text for word in ("?", "suppose", "why", "should", "if ", "would", "what if", "can i", "could i")):
        return False
    patterns = (
        "i surrender", "i give up", "i concede", "i yield", "i admit defeat",
        "you have defeated me", "you defeated me", "you win", "i cannot refute your position",
        "i can't refute your position", "i cannot refute you", "i can't refute you",
    )
    return any(text.startswith(pattern) or f" {pattern}" in text for pattern in patterns)


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
    try:
        await open_session(state)
    except AgentCallError as exc:
        audit_event(AUDIT_PATH, "philosopher_model_error", session_id=session_id, philosopher=state.philosopher)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    SESSIONS[session_id] = state
    audit_event(AUDIT_PATH, "session_started", session_id=session_id, philosopher="plato")
    return public_state(state)


@app.post("/api/sessions/{session_id}/revisit/{philosopher}")
async def create_revisit(session_id: str, philosopher: str) -> dict:
    campaign = SESSIONS.get(session_id)
    if not campaign:
        raise HTTPException(404, "Campaign session not found")
    if philosopher not in PHILOSOPHERS:
        raise HTTPException(404, "Philosopher not found")
    if philosopher not in campaign.persuaded:
        raise HTTPException(403, "This philosopher has not been persuaded yet.")

    revisit_id = uuid.uuid4().hex
    revisit = GameState(
        session_id=revisit_id,
        philosopher_index=PHILOSOPHERS.index(philosopher),
        is_revisit=True,
        campaign_session_id=campaign.session_id,
    )
    try:
        await open_session(revisit)
    except AgentCallError as exc:
        audit_event(AUDIT_PATH, "philosopher_model_error", session_id=revisit_id, philosopher=revisit.philosopher)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    SESSIONS[revisit_id] = revisit
    audit_event(
        AUDIT_PATH,
        "revisit_started",
        session_id=revisit_id,
        campaign_session_id=campaign.session_id,
        philosopher=philosopher,
    )
    return {"state": public_state(revisit)}


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
    if state.complete and not state.victory_pending:
        raise HTTPException(409, "The Lyceum has been completed.")
    if state.transition_pending:
        raise HTTPException(409, "Continue to the next encounter before speaking again.")
    message = validate_player_message(request.message)
    injection_attempt = looks_like_prompt_injection(message)
    if injection_attempt:
        audit_event(AUDIT_PATH, "injection_blocked", session_id=session_id, philosopher=state.philosopher)
        raise HTTPException(
            status_code=400,
            detail="Instruction override requests are blocked. Continue with a question or philosophical argument.",
        )
    budget = Budget(requests=state.budget_requests, output_tokens=state.budget_output_tokens)
    surrender = is_explicit_surrender(message) and not state.victory_pending and not state.is_revisit
    try:
        reply, _ = await philosopher_turn(state, message, budget, surrender=surrender)
    except AgentCallError as exc:
        state.budget_requests = budget.requests
        state.budget_output_tokens = budget.output_tokens
        audit_event(AUDIT_PATH, "philosopher_model_error", session_id=session_id, philosopher=state.philosopher)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    result = None if surrender or state.victory_pending or state.is_revisit else await evaluate(state, message, reply, budget)
    display_reply = visible_reply(reply)
    state.messages.extend([{"role": "user", "content": message}, {"role": "assistant", "content": display_reply}])
    state.budget_requests = budget.requests
    state.budget_output_tokens = budget.output_tokens
    advanced = False
    belief = None
    outcome = "none"
    if surrender and state.philosopher not in state.surrendered and state.philosopher not in state.persuaded:
        state.surrendered.append(state.philosopher)
        state.philosopher_index += 1
        state.transition_pending = True
        advanced = True
        outcome = "surrender"
    elif not state.is_revisit and result and result.get("persuaded") and state.philosopher not in state.persuaded:
        belief = str(result.get("belief") or "a stated commitment")[:200]
        state.persuaded.append(state.philosopher)
        state.victory_pending = True
        advanced = True
        outcome = "victory"
    audit_event(
        AUDIT_PATH,
        "turn_completed",
        session_id=session_id,
        philosopher=state.philosopher,
        advanced=advanced,
        requests=budget.requests,
    )
    return {"reply": display_reply, "evaluation": result, "advanced": advanced, "outcome": outcome, "belief": belief, "state": public_state(state)}


@app.post("/api/sessions/{session_id}/continue")
async def continue_session(session_id: str) -> dict:
    """Commit the UI transition and open a fresh conversation for the next philosopher."""
    state = SESSIONS.get(session_id)
    if not state:
        raise HTTPException(404, "Session not found")
    if state.is_revisit:
        raise HTTPException(409, "Return to the journey instead of continuing a revisit.")
    if not state.transition_pending and not state.victory_pending:
        raise HTTPException(409, "There is no pending encounter transition.")

    if state.victory_pending:
        state.philosopher_index += 1
        state.victory_pending = False
        state.transition_pending = True

    if state.complete:
        state.messages = []
        state.transition_pending = False
        return {"state": public_state(state)}

    # Reset the model context before generating the next opening. If the model
    # call fails, the empty context and pending flag make a retry safe.
    state.messages = []
    budget = Budget(requests=state.budget_requests, output_tokens=state.budget_output_tokens)
    try:
        opening, _ = await philosopher_turn(
            state,
            session_opening_prompt(),
            budget,
        )
    except AgentCallError as exc:
        state.budget_requests = budget.requests
        state.budget_output_tokens = budget.output_tokens
        audit_event(AUDIT_PATH, "philosopher_model_error", session_id=session_id, philosopher=state.philosopher)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    state.messages.append({"role": "assistant", "content": visible_reply(opening)})
    state.budget_requests = budget.requests
    state.budget_output_tokens = budget.output_tokens
    state.transition_pending = False
    audit_event(AUDIT_PATH, "encounter_started", session_id=session_id, philosopher=state.philosopher)
    return {"state": public_state(state)}


@app.post("/api/sessions/{session_id}/return")
async def return_to_campaign(session_id: str) -> dict:
    revisit = SESSIONS.get(session_id)
    if not revisit:
        raise HTTPException(404, "Revisit session not found")
    if not revisit.is_revisit or not revisit.campaign_session_id:
        raise HTTPException(409, "This is already the campaign session.")
    campaign = SESSIONS.get(revisit.campaign_session_id)
    if not campaign:
        raise HTTPException(404, "Campaign session not found")
    return {"state": public_state(campaign)}
