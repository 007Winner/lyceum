"""Rebuild the included Gutenberg corpus and local FTS5 index.

The repository includes the downloaded text files. Use --download only when
refreshing them from the recorded Gutenberg URLs; use --index after editing a
text or sources.json.
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT))


def download() -> None:
    sources = json.loads((DATA / "sources.json").read_text(encoding="utf-8"))
    for source in sources:
        if source.get("availability") != "available" or not source.get("local_path"):
            continue
        target = DATA / source["local_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(source["source_url"], headers={"User-Agent": "The Lyceum educational project"})
        with urllib.request.urlopen(request, timeout=60) as response:
            target.write_bytes(response.read())
        print(f"downloaded {source['title']} -> {target}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--index", action="store_true")
    args = parser.parse_args()
    if args.download:
        download()
    if args.index or not args.download:
        from backend.retrieval import build_index

        print(f"indexed {build_index()} passages")


if __name__ == "__main__":
    main()
