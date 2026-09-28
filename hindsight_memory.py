"""Real Hindsight Cloud memory for MemReview."""

import os
from typing import Any

from dotenv import load_dotenv
from hindsight_client import Hindsight

load_dotenv()
BANK = "team-code-review"


class HindsightConfigurationError(RuntimeError):
    pass


class HindsightServiceError(RuntimeError):
    pass


_client: Hindsight | None = None


def get_client() -> Hindsight:
    """Create one reusable authenticated Hindsight Cloud client."""
    global _client
    api_key = os.getenv("HINDSIGHT_API_KEY")
    base_url = os.getenv("HINDSIGHT_BASE_URL")
    if not api_key or not base_url:
        raise HindsightConfigurationError(
            "Hindsight is not configured. Add HINDSIGHT_API_KEY and HINDSIGHT_BASE_URL to .env, then restart the server."
        )
    if _client is None:
        _client = Hindsight(base_url=base_url, api_key=api_key)
    return _client


def ensure_bank() -> None:
    """Create the Hindsight bank on the first seed; ignore an existing bank."""
    try:
        get_client().create_bank(bank_id=BANK, name="MemReview Team Code Review")
    except HindsightConfigurationError:
        raise
    except Exception as error:
        message = str(error).lower()
        if "already exists" not in message and "409" not in message and "conflict" not in message:
            raise HindsightServiceError(
                f"Could not create the Hindsight memory bank. Details: {error}"
            ) from error


def retain_memory(content: str, context: str, document_id: str | None = None) -> None:
    """Store a team decision or a human reviewer correction."""
    try:
        options: dict[str, Any] = {"bank_id": BANK, "content": content, "context": context}
        if document_id:
            options["document_id"] = document_id
        get_client().retain(**options)
    except HindsightConfigurationError:
        raise
    except Exception as error:
        raise HindsightServiceError(
            f"Hindsight could not save this learning. Check the API key and Cloud credits. Details: {error}"
        ) from error


def recall_memories(query: str) -> list[dict[str, str]]:
    """Retrieve the team decisions relevant to a code diff."""
    try:
        response = get_client().recall(bank_id=BANK, query=query, budget="high", max_tokens=2500)
        return [
            {
                "id": str(item.id),
                "text": item.text,
                "context": item.context or "Team memory",
            }
            for item in response.results
        ]
    except HindsightConfigurationError:
        raise
    except Exception as error:
        raise HindsightServiceError(
            f"Hindsight could not recall team memory. Check the API key and Cloud credits. Details: {error}"
        ) from error
