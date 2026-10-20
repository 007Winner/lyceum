"""Summarize token_usage.csv without requiring provider pricing."""
from __future__ import annotations

import csv
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "analysis" / "token_usage.csv"
SUMMARY_PATH = ROOT / "analysis" / "tokenomics_summary.md"
CHART_PATH = ROOT / "analysis" / "tokenomics_chart.png"


def number(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, "") or 0)
    except ValueError:
        return 0.0


def rate(name: str) -> float | None:
    raw = os.getenv(name, "").strip()
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def make_chart(rows: list[dict[str, str]]) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        _make_png_without_pillow(rows)
        return

    width, height = 1100, 620
    image = Image.new("RGB", (width, height), "#171116")
    draw = ImageDraw.Draw(image)
    draw.text((55, 35), "The Lyceum token usage", fill="#e6ba70")
    if not rows:
        draw.text((55, 290), "No live usage rows recorded yet.", fill="#f8ecd8")
        image.save(CHART_PATH)
        return
    groups: dict[str, list[float]] = {}
    for row in rows:
        groups.setdefault(row.get("agent_role", "unknown"), []).append(number(row, "output_tokens"))
    maximum = max(max(values) for values in groups.values()) or 1
    baseline = 520
    bar_width = 190
    for index, (role, values) in enumerate(sorted(groups.items())):
        average = sum(values) / len(values)
        x = 170 + index * 300
        top = baseline - int(average / maximum * 350)
        draw.rectangle((x, top, x + bar_width, baseline), fill="#8f304b", outline="#e6ba70")
        draw.text((x + 20, baseline + 18), role, fill="#f8ecd8")
        draw.text((x + 20, top - 25), f"{average:.1f} output", fill="#e6ba70")
    image.save(CHART_PATH)


def _make_png_without_pillow(rows: list[dict[str, str]]) -> None:
    """Write a dependency-free bar chart fallback (RGB PNG)."""
    import struct
    import zlib

    width, height = 900, 500
    pixels = bytearray([23, 17, 22] * width * height)
    groups: dict[str, list[float]] = {}
    for row in rows:
        groups.setdefault(row.get("agent_role", "unknown"), []).append(number(row, "output_tokens"))
    values = [sum(v) / len(v) for v in groups.values()] or [0]
    maximum = max(values) or 1
    for index, value in enumerate(values):
        x0, x1 = 150 + index * 260, 340 + index * 260
        top = 430 - int(value / maximum * 300)
        for y in range(top, 430):
            for x in range(x0, min(x1, width)):
                offset = (y * width + x) * 3
                pixels[offset:offset + 3] = bytes((143, 48, 75))
    raw = b"".join(b"\x00" + bytes(pixels[y * width * 3:(y + 1) * width * 3]) for y in range(height))
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    CHART_PATH.write_bytes(png)


def main() -> None:
    rows = []
    if CSV_PATH.exists():
        with CSV_PATH.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    roles = sorted({row.get("agent_role", "unknown") for row in rows})
    lines = [
        "# Tokenomics summary",
        "",
        f"Rows measured: **{len(rows)}**. Source: `analysis/token_usage.csv`.",
        "",
        "The logger records provider-reported input, cached input, cache-write, output, total tokens, duration, model, role, and an optional estimated cost. It never records prompts, responses, or API keys.",
        "",
        "| Agent role | Calls | Avg input | Avg cached input | Avg output | Avg total | Avg duration (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for role in roles:
        subset = [row for row in rows if row.get("agent_role") == role]
        n = len(subset)
        lines.append(f"| {role} | {n} | {sum(number(r,'input_tokens') for r in subset)/n:.1f} | {sum(number(r,'cached_input_tokens') for r in subset)/n:.1f} | {sum(number(r,'output_tokens') for r in subset)/n:.1f} | {sum(number(r,'total_tokens') for r in subset)/n:.1f} | {sum(number(r,'duration_ms') for r in subset)/n:.1f} |" )
    lines += [
        "",
        "## Rates and cost",
        "",
        "No verified GPT-6 Luna rates were found in the repository or provider response metadata. The optional environment variables `LYCEUM_INPUT_RATE_PER_MILLION`, `LYCEUM_CACHED_INPUT_RATE_PER_MILLION`, and `LYCEUM_OUTPUT_RATE_PER_MILLION` remain unset, so estimated cost is blank rather than invented.",
        "",
        "Once verified rates are supplied, cost is calculated as `(uncached input × input rate + cached input × cached rate + cache-write input × input rate + output × output rate) / 1,000,000`. Complete-playthrough and 1/100/10,000-user projections are extrapolations from measured rows and an explicitly chosen number of monthly playthroughs; they are not observed usage.",
        "",
        "## Limitations",
        "",
        "Existing acceptance JSON contains completion-token measurements but not provider input/cache metadata. New CSV rows are required for measured input and cache analysis. Logging is best effort and cannot interrupt gameplay.",
    ]
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    make_chart(rows)
    print(f"{len(rows)} usage rows; wrote {SUMMARY_PATH} and {CHART_PATH}")


if __name__ == "__main__":
    main()
