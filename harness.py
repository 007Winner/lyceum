"""Safety and budget policy for the Lyceum agent loop."""

from dataclasses import dataclass
import re

MAX_OUTPUT_TOKENS = 420
MAX_INPUT_CHARS = 5_000
MAX_TOTAL_REQUESTS = 120
MAX_DELEGATION_DEPTH = 1


@dataclass
class Budget:
    requests: int = 0
    output_tokens: int = 0

    def allow(self, request_count: int = 1) -> bool:
        return self.requests + request_count <= MAX_TOTAL_REQUESTS

    def consume(self, request_count: int = 1, output_tokens: int = 0) -> None:
        if not self.allow(request_count):
            raise BudgetExceeded("session request budget reached")
        self.requests += request_count
        self.output_tokens += output_tokens


class BudgetExceeded(RuntimeError):
    """Raised before a model call would exceed the session budget."""


def validate_player_message(message: str) -> str:
    cleaned = " ".join(message.strip().split())
    if not cleaned:
        raise ValueError("Message cannot be empty.")
    if len(cleaned) > MAX_INPUT_CHARS:
        raise ValueError(f"Message is limited to {MAX_INPUT_CHARS} characters.")
    return cleaned


def looks_like_prompt_injection(message: str) -> bool:
    """Catch common attempts to replace the game's instructions before a call."""
    patterns = (
        r"ignore\s+(all\s+)?previous",
        r"reveal\s+(the\s+)?(system|developer|hidden)\s+prompt",
        r"show\s+me\s+your\s+(instructions|prompt)",
        r"pretend\s+(i|that)\s+(won|you were persuaded)",
        r"ignore\s+(the\s+)?rules",
        r"unlock\s+(the\s+)?(next|aristotle|philosopher)",
    )
    return any(re.search(pattern, message, flags=re.IGNORECASE) for pattern in patterns)
