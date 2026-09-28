# MemReview — AI Code Reviewer with Real Team Memory

MemReview shows the difference between a generic AI code review and a review
that recalls a team's historical pull-request decisions. Human feedback is
retained in Hindsight Cloud, so a rejection with a new rule changes future
reviews.

## One-time Hindsight setup

1. Sign up at https://ui.hindsight.vectorize.io.
2. Open **Billing** and apply promo code `MEMHACK99` for the hackathon credits.
3. Open **Connect → Create API Key** and copy the key immediately; it is shown only once.
4. In the project's existing `.env`, keep the Groq key and add these exact lines:

   ```env
   HINDSIGHT_API_KEY=your_hindsight_key
   HINDSIGHT_BASE_URL=https://api.hindsight.vectorize.io
   ```

Do not commit `.env` or share either key.

## Run locally

1. Install Python 3.10+.
2. Open this folder in VS Code and open its terminal.
3. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   ```

   Windows:

   ```powershell
   venv\Scripts\activate
   ```

   macOS/Linux:

   ```bash
   source venv/bin/activate
   ```

4. Install dependencies, including the official Hindsight client:

   ```bash
   pip install -r requirements.txt
   ```

   If needed, the direct command is:

   ```bash
   pip install hindsight-client
   ```

5. Seed the four historical team decisions into the real Hindsight Cloud bank:

   ```bash
   python seed_memory.py
   ```

6. Start the API:

   ```bash
   uvicorn main:app --reload
   ```

7. Open `frontend/index.html` with VS Code Live Server. Ensure **Demo mode is unticked**.

## What changed

- `memory_store.json` is now seed data only, with realistic PR numbers, authors, and dates.
- `seed_memory.py` uses Hindsight `retain()` to store PR #42, #37, #51, and #18 in the `team-code-review` bank.
- `POST /review` uses Hindsight `recall()` instead of local keyword matching.
- `POST /feedback` calls Hindsight `retain()` for both acceptance reinforcement and human corrections. A Reject requires a note.
- The UI displays useful errors for an empty diff, a missing Hindsight key, service failures, and missing reject notes.

## 60-second demo story

1. Open **PR #58** and run **Review: Without vs With Memory**.
2. Point out that the left result is generic while the right result cites **PR #42** for the Tailwind rule.
3. Switch to **PR #64**. Click **Reject and teach** and enter:

   ```text
   We also require type hints for all new helper functions.
   ```

4. Wait up to 60 seconds for Hindsight Cloud to process the retained feedback, then run PR #64 again.
5. Show that the personalized review now applies the new type-hints convention.

## API

`POST /review`

```json
{
  "diff": "def get_user(user_id): ...",
  "use_memory": true,
  "pull_request": {
    "title": "PR #64: Add customer lookup endpoint",
    "author": "Daniel Kim",
    "date": "2026-09-25"
  }
}
```

The response preserves the frontend's existing `review` and `memories` keys.

`POST /feedback`

```json
{
  "action": "rejected",
  "note": "We also require type hints for all new helper functions.",
  "review": "...",
  "diff": "..."
}
```
