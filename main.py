import json
import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq

from hindsight_memory import (
    HindsightConfigurationError,
    HindsightServiceError,
    recall_memories,
    retain_memory,
)

load_dotenv()

app = FastAPI(title="MemReview API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your frontend domain before production deployment.
    allow_methods=["*"],
    allow_headers=["*"],
)

groq_api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=groq_api_key) if groq_api_key else None
AUDIT_LOG = Path(__file__).with_name("feedback_log.json")


def require_text(body: dict, key: str, error_message: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(status_code=400, detail=error_message)
    return value.strip()


def append_audit_log(event: dict) -> None:
    """Optional audit trail. Hindsight is the real learning store."""
    with AUDIT_LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event) + "\n")


@app.get("/")
@app.get("/health")
def health():
    return {
        "status": "ok",
        "groq_configured": bool(groq_api_key),
        "hindsight_configured": bool(os.getenv("HINDSIGHT_API_KEY")),
    }


@app.post("/review")
def review(body: dict):
    diff = require_text(body, "diff", "Paste a pull-request diff before starting the review.")
    use_memory = body.get("use_memory", True)
    pull_request = body.get("pull_request") or {}
    pr_title = pull_request.get("title") or "Untitled pull request"
    pr_author = pull_request.get("author") or "Unknown author"
    pr_date = pull_request.get("date") or "Unknown date"

    recalled: list[dict[str, str]] = []
    if use_memory:
        query = f"""Review this pull request and retrieve only relevant previous team decisions.
PR title: {pr_title}
Author: {pr_author}
Date: {pr_date}
Code diff:
{diff[:8000]}
"""
        try:
            recalled = recall_memories(query)
        except HindsightConfigurationError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except HindsightServiceError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    memory_text = "\n".join(
        f"- Source: {memory['context']}\n  Rule: {memory['text']}" for memory in recalled
    )
    if not memory_text:
        memory_text = "No relevant team memory was found. Give a standard code review."

    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Groq is not configured. Add GROQ_API_KEY to .env, then restart the server.",
        )

    prompt = f"""You are a senior code reviewer.

PULL REQUEST
Title: {pr_title}
Author: {pr_author}
Date: {pr_date}

RECALLED TEAM MEMORY
{memory_text}

CODE DIFF
{diff}

Instructions:
- Review only real issues in this diff.
- Apply recalled team rules only when relevant.
- If using a rule, cite its source exactly, for example: "Team decision in PR #42: ...".
- Do not invent rules or PR numbers.
- Give concise, actionable bullet points with severity where useful.
"""

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"The review model could not generate a response: {error}",
        ) from error

    return {
        "review": response.choices[0].message.content,
        "cited_memories": [memory["id"] for memory in recalled],
        "memories": [memory["text"] for memory in recalled],
        "memory_used": bool(recalled),
        "memory_message": (
            f"Recalled {len(recalled)} relevant team memories from Hindsight."
            if recalled
            else "No matching team memory found — showing a standard review."
        ),
    }


@app.post("/feedback")
def feedback(body: dict):
    action = require_text(body, "action", "Choose Accept or Reject before submitting feedback.")
    if action not in {"accepted", "rejected"}:
        raise HTTPException(status_code=400, detail="Feedback action must be either accepted or rejected.")

    review = require_text(body, "review", "No review content was provided for feedback.")
    diff = require_text(body, "diff", "No pull-request diff was provided for feedback.")
    note = (body.get("note") or "").strip()
    if action == "rejected" and not note:
        raise HTTPException(
            status_code=400,
            detail="Add a note explaining the rule the reviewer should learn before rejecting.",
        )

    review_id = body.get("review_id") or str(uuid4())
    pull_request = body.get("pull_request") or {}
    pr_title = pull_request.get("title") or "Untitled pull request"
    pr_author = pull_request.get("author") or "Unknown author"

    if action == "rejected":
        learning = f"""Human reviewer correction for {pr_title} by {pr_author}.
The AI review was rejected. New team rule:
{note}

Apply this rule to future relevant code reviews.
Related diff:
{diff[:4000]}
"""
    else:
        learning = f"""Human reviewer accepted an AI review for {pr_title} by {pr_author}.
Accepted review:
{review}

This reinforces the team conventions used in the review.
"""

    try:
        retain_memory(
            content=learning,
            context=f"Human reviewer feedback | {action} | review {review_id}",
            document_id=f"feedback-{review_id}",
        )
    except HindsightConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except HindsightServiceError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    append_audit_log(
        {
            "review_id": review_id,
            "action": action,
            "note": note,
            "pull_request": pull_request,
        }
    )
    return {
        "status": "saved",
        "learned": True,
        "message": (
            "New team rule saved to Hindsight. Run another relevant review to see it applied."
            if action == "rejected"
            else "Accepted review retained in Hindsight as reinforcement for future reviews."
        ),
    }
