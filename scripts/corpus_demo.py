"""Run three primary-text retrieval conversations for every philosopher."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.retrieval import search, retrieve_context  # noqa: E402


SCENARIOS = {
    "plato": ["justice in a city", "Socrates and the examined life", "love and beauty"],
    "aristotle": ["virtue habit happiness", "citizenship and constitutions", "tragedy and imitation"],
    "machiavelli": ["fortune and virtù", "arms and rulers", "republics and conflict"],
    "hume": ["cause effect experience", "custom and belief", "design and natural religion"],
    "kant": ["duty universal law", "space and time knowledge", "Prolegomena metaphysics science"],
}


def main() -> None:
    evidence: list[dict] = []
    for philosopher, queries in SCENARIOS.items():
        for query in queries:
            passages = search(philosopher, query, limit=3)
            retrieve_context(philosopher, query, limit=3)
            evidence.append(
                {
                    "philosopher": philosopher,
                    "player_message": query,
                    "retrieved_passages": [
                        {"work": p.work, "chunk_id": p.chunk_id, "source_url": p.source_url} for p in passages
                    ],
                    "how_used": "reference-only context supplied to the philosopher prompt; evaluator receives no corpus text",
                }
            )
    target = ROOT / "output" / "corpus_demo.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(evidence)} retrieval conversations to {target}")


if __name__ == "__main__":
    main()
