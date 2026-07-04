#!/usr/bin/env python3
"""Extract only sent messages from a debug log.

This filters the log down to lines emitted when an adapter actually sends or
receives a message, ignoring message history, enabled sets, and LLM reasoning
text.

Usage:
    python debug_scripts/extract_message_trace.py <log_file> [--json]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


MESSAGE_LINE_RE = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\s+-\s+DEBUG\s+-\s+DEBUG:\s+(?P<direction>Sending|Received)\s+message:\s+(?P<message>.+?)\s*$"
)


def extract_message_trace(log_text: str) -> list[dict[str, str]]:
    """Return only the actual message trace entries from the log."""

    trace: list[dict[str, str]] = []
    for line in log_text.splitlines():
        match = MESSAGE_LINE_RE.match(line)
        if match:
            trace.append(
                {
                    "timestamp": match.group("timestamp"),
                    "direction": match.group("direction").lower(),
                    "message": match.group("message"),
                }
            )
    return trace


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_file", type=Path, help="Path to the debug log file")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the extracted trace as JSON instead of plain text",
    )
    args = parser.parse_args()

    log_text = args.log_file.read_text(encoding="utf-8", errors="ignore")
    trace = extract_message_trace(log_text)

    if args.json:
        print(json.dumps(trace, indent=2, ensure_ascii=False))
    else:
        for item in trace:
            print(f"{item['timestamp']}  {item['direction']}: {item['message']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())