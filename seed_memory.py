"""Seed the historical PR decisions into Hindsight Cloud.

After putting the Hindsight key in .env, run once:
    python seed_memory.py
"""

import json
from pathlib import Path

from hindsight_memory import HindsightConfigurationError, HindsightServiceError, ensure_bank, retain_memory

MEMORY_FILE = Path(__file__).with_name("memory_store.json")


def main() -> None:
    rules = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    try:
        ensure_bank()
        for rule in rules:
            content = (
                f"Historical pull-request decision. {rule['source_pr']} | "
                f"{rule['date']} | Author: {rule['author']}.\n"
                f"Team rule: {rule['rule']}\n"
                f"Why it matters: {rule['rationale']}"
            )
            retain_memory(
                content=content,
                context=f"{rule['source_pr']} — historical team decision",
                document_id=rule["id"],
            )
            print(f"Retained {rule['source_pr']}: {rule['rule']}")
    except (HindsightConfigurationError, HindsightServiceError) as error:
        raise SystemExit(f"Seeding failed: {error}") from error


if __name__ == "__main__":
    main()
