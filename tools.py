"""Small deterministic tools shared by the agents and API."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

PHILOSOPHERS = ("plato", "aristotle", "machiavelli", "hume", "kant")


class GameState(BaseModel):
    session_id: str
    philosopher_index: int = 0
    persuaded: list[str] = Field(default_factory=list)
    surrendered: list[str] = Field(default_factory=list)
    messages: list[dict[str, str]] = Field(default_factory=list)
    victory_pending: bool = False
    transition_pending: bool = False
    budget_requests: int = 0
    budget_output_tokens: int = 0

    @property
    def philosopher(self) -> str:
        return PHILOSOPHERS[min(self.philosopher_index, len(PHILOSOPHERS) - 1)]

    @property
    def complete(self) -> bool:
        return len(set(self.persuaded) | set(self.surrendered)) == len(PHILOSOPHERS)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit_event(path: Path, event: str, **data: object) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": now_iso(), "event": event, **data}, ensure_ascii=True) + "\n")
