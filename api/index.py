"""Vercel entry point for The Lyceum FastAPI service.

Vercel strips the ``/api`` function prefix before handing the request to an
ASGI app. The production API keeps its explicit ``/api`` routes, so this
small adapter restores that prefix without changing the application itself.
"""

from pathlib import Path

from backend import agents as backend_agents
from backend import main as backend_main
from backend import retrieval as backend_retrieval

# Vercel's deployed filesystem is read-only except for /tmp. Keep the
# application's observability writes working without changing game behavior.
backend_main.AUDIT_PATH = Path("/tmp/lyceum-audit.jsonl")
backend_agents.USAGE_PATH = Path("/tmp/lyceum-token-usage.csv")
backend_retrieval.RETRIEVAL_LOG = Path("/tmp/lyceum-retrieval.jsonl")
backend_app = backend_main.app

# The public static frontend uses this stable Vercel alias. Add it to the
# existing allow-list so browser requests can reach the API.
for middleware in backend_app.user_middleware:
    if "allow_origins" in middleware.kwargs:
        middleware.kwargs["allow_origins"] = [
            *middleware.kwargs["allow_origins"],
            "https://the-lyceum-pied.vercel.app",
        ]


async def app(scope, receive, send):
    if scope["type"] == "http" and not scope["path"].startswith("/api"):
        scope = dict(scope)
        scope["path"] = "/api" + (scope["path"] or "/")
    await backend_app(scope, receive, send)


__all__ = ["app"]
