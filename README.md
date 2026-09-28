# 🧠 MemReview: A Code Review & Architecture Standards Agent with Long-Term Memory

> An AI pull-request reviewer that **remembers** your team's past review feedback, architectural decisions, and recurring bugs, and gets smarter with every PR.

---

## 1. Problem Statement

**Option 1: Code Review & Architecture Standards Agent (Engineering & DevOps)**

An AI code reviewer that connects to GitHub/GitLab pull requests. Over time, it remembers your team's pull request feedback, architectural conventions, preferred design patterns, and past recurring bugs.

**Why Hindsight memory shines**

| Interaction | Behaviour |
|---|---|
| **1** | Generic linter/syntax feedback, like any standard LLM. |
| **5** | Recalls past PR comments: *"In PR #42, your team explicitly decided to avoid inline CSS in favour of Tailwind classes, and required null checks on API parameters."* |
| **15** | Automatically flags recurring architectural violations and anti-patterns based on past team discussions. |

**Why it matters:** Engineering teams spend hours repeating the same PR comments. An agent that reduces review cycles has direct, measurable ROI.

---

## 2. The Problem in Plain Words

Today's AI code reviewers are **stateless**. Every PR is reviewed as if it is the first one ever. They do not know:

- that your team banned inline CSS three months ago,
- that reviewers always ask for null checks on API inputs,
- that the same `SELECT *` mistake has appeared in 6 PRs,
- that a senior engineer rejected a suggestion last week, so it should not be suggested again.

Human reviewers end up typing the same comments again and again. New joiners repeat old mistakes because tribal knowledge lives in old PR threads nobody re-reads.

**Our solution:** give the reviewer a **persistent memory** of everything the team has decided, corrected, accepted, or rejected, and use it on every new PR.

---

## 3. What We Are Building (One-Paragraph Summary)

MemReview is a GitHub App / webhook service. When a pull request is opened or updated, it reads the diff, **recalls** relevant team memories (past comments, conventions, recurring bugs), asks an LLM to review the code **with that memory as context**, and posts inline comments that cite the earlier PR or decision. When humans reply, resolve, or dismiss those comments, the agent **learns from that feedback** and stores it. After enough repetitions, it promotes repeated feedback into **explicit team rules** and starts flagging violations automatically.

---

## 4. Core Concept: The Three Memory Operations

We use a Hindsight-style agent memory layer with three operations:

| Operation | Meaning | In our project |
|---|---|---|
| **Retain** | Store new information | Save PR comments, review outcomes, decisions, bug patterns |
| **Recall** | Retrieve relevant memory | Before reviewing a diff, fetch the most relevant past feedback |
| **Reflect** | Consolidate and reason over memory | Turn repeated feedback into rules, raise or lower confidence, drop stale rules |

> ⚠️ **Team note:** Confirm the exact API names and SDK of the Hindsight memory library given at the hackathon and map `retain / recall / reflect` to them. The design below stays the same either way.

### Memory types we store

| Type | Example | Source |
|---|---|---|
| **Convention** | "Use Tailwind classes, not inline CSS" | Reviewer comments |
| **Architectural decision** | "All DB access goes through the repository layer" | PR discussions |
| **Recurring bug** | "Missing null check on API params" (seen 5×) | Repeated review comments |
| **Feedback outcome** | "Suggestion X was rejected by @lead" | Comment resolved/dismissed/👎 |
| **Author/file pattern** | "`payments/` files often miss error handling" | Aggregated history |

---

## 5. System Architecture & Pipeline

<img width="2440" height="1800" alt="architecture" src="https://github.com/user-attachments/assets/abc6b760-1493-4696-adee-4b60c84aeec0" />


### Step-by-step pipeline

**Step 0: Bootstrap (one-time, "cold start")**
Import the last N closed PRs and their review comments from GitHub API. Each comment becomes a raw memory. This gives the agent a history to learn from before the first live PR.

**Step 1: Ingest PR**
GitHub sends a `pull_request` (opened/synchronize) webhook. We fetch the diff, changed files, PR title/description.

**Step 2: Parse diff**
Split the diff into **hunks** (small logical chunks). Detect language and, where possible, parse with **tree-sitter** to extract functions, classes, API handlers, and JSX/HTML elements. This lets us attach the right memory to the right code.

**Step 3: Recall**
For each hunk, build a query (code text + file path + detected patterns) and retrieve top-k relevant memories using **hybrid retrieval** (see §6). Also pull all active **rules** that match the file path or language.

**Step 4: Rule check (fast, deterministic)**
Run promoted rules first (e.g., regex or AST checks such as "inline `style=` attribute in JSX", "route handler without parameter validation"). These are cheap and precise.

**Step 5: LLM review with memory**
Prompt the LLM with: the hunk, the recalled memories (with PR numbers and who said what), active rules, and instructions to cite the source. Output is structured JSON: `{file, line, severity, comment, cited_memory_id}`.

**Step 6: Rank & dedupe**
Merge rule findings and LLM findings, remove duplicates, drop anything the team previously rejected, cap at a sensible number of comments, order by severity and confidence.

**Step 7: Post review**
Post inline comments via GitHub API. Every memory-based comment includes a citation, e.g. *"Per PR #42 (@priya): avoid inline CSS, use Tailwind."*

**Step 8: Feedback capture (Retain)**
Listen for: reply comments, "resolved", 👍/👎 reactions, and whether the author actually changed the code in the next commit. Store the outcome linked to the original memory.

**Step 9: Reflect (scheduled)**
A periodic job clusters similar feedback, promotes repeated ones into rules, updates confidence, and retires stale rules.

---

## 6. Algorithms & Techniques Used

| # | Technique | Where used | Why |
|---|---|---|---|
| 1 | **Diff hunk chunking** | Diff parser | Small, focused units retrieve better memories than whole files |
| 2 | **AST parsing (tree-sitter)** | Diff parser, rule engine | Understand code structure (function, handler, JSX) instead of raw text |
| 3 | **Text embeddings + cosine similarity** | Recall | Semantic match between new code and past comments |
| 4 | **BM25 keyword search** | Recall | Catches exact terms (`null`, `SELECT *`, `style=`) that embeddings can miss |
| 5 | **Reciprocal Rank Fusion (RRF)** | Recall | Combines vector and BM25 rankings into one list |
| 6 | **Metadata filtering** | Recall | Restrict by repo, language, file path, memory type |
| 7 | **Recency-weighted scoring** | Recall ranking | Newer decisions override older ones (exponential time decay) |
| 8 | **Clustering (agglomerative / threshold-based on embeddings)** | Reflect | Group similar recurring comments |
| 9 | **Frequency-threshold rule promotion** | Reflect | If a cluster appears in ≥ 3 PRs by ≥ 2 reviewers → becomes a rule |
| 10 | **Confidence scoring** | Reflect, ranking | `confidence = (accepted + 1) / (accepted + rejected + 2)` (Laplace smoothing) |
| 11 | **Conflict resolution** | Reflect | If two memories contradict, prefer newer and higher-seniority; flag for human confirmation |
| 12 | **Prompt engineering / RAG** | LLM reviewer | Inject retrieved memories with citations into the prompt |
| 13 | **Structured output (JSON schema)** | LLM reviewer | Reliable, parseable review comments |
| 14 | **Deduplication (embedding similarity threshold)** | Ranker | Avoid repeating the same comment across hunks |

### Key formulas

**Final retrieval score**

```
score = 0.5 * semantic_similarity
      + 0.2 * bm25_score_normalized
      + 0.2 * recency_weight
      + 0.1 * confidence

recency_weight = exp(-λ * age_in_days)      # λ ≈ 0.01, tune later
```

**Rule confidence**

```
confidence = (accepted_count + 1) / (accepted_count + rejected_count + 2)
```

A rule is **active** if confidence ≥ 0.6 and it was seen in ≥ 3 PRs. It is **retired** if confidence drops below 0.3 or it has not fired in 90 days.

---

## 7. Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11 |
| Web server | FastAPI + Uvicorn |
| Git integration | GitHub App / Webhooks + `PyGithub` (GitLab optional) |
| Memory layer | **Hindsight** (retain / recall / reflect) |
| Vector store | Whatever Hindsight uses, or Chroma / FAISS as fallback |
| Keyword search | `rank_bm25` |
| Embeddings | Sentence-Transformers (`all-MiniLM-L6-v2`) or provider embeddings |
| Code parsing | `tree-sitter` |
| LLM | Any chat LLM (Claude / GPT / open model) via API |
| DB (metadata, feedback log) | SQLite (upgrade to Postgres if time) |
| Dashboard | Streamlit (memory timeline, rules, metrics) |
| Local webhook testing | ngrok |
| Deployment | Docker + Render / Railway |

---

## 8. Project Structure

```
memreview/
├── README.md
├── architecture.png
├── requirements.txt
├── .env.example                 # GITHUB_TOKEN, WEBHOOK_SECRET, LLM_API_KEY, MEMORY_API_KEY
├── docker-compose.yml
│
├── app/
│   ├── main.py                  # FastAPI entrypoint
│   ├── config.py                # env + settings
│   │
│   ├── api/
│   │   ├── webhook.py           # receives GitHub PR + comment events
│   │   └── dashboard_api.py     # endpoints for the UI
│   │
│   ├── github/
│   │   ├── client.py            # fetch diff, post comments, list past PRs
│   │   └── bootstrap.py         # import historical PR comments (cold start)
│   │
│   ├── parsing/
│   │   ├── diff_parser.py       # diff → hunks
│   │   └── ast_utils.py         # tree-sitter helpers
│   │
│   ├── memory/
│   │   ├── store.py             # wrapper over Hindsight: retain / recall / reflect
│   │   ├── schemas.py           # Memory, Rule, FeedbackEvent models
│   │   ├── retrieval.py         # hybrid search + RRF + recency scoring
│   │   ├── reflect.py           # clustering, rule promotion, decay
│   │   └── conflict.py          # contradiction handling
│   │
│   ├── rules/
│   │   ├── engine.py            # runs active rules on hunks
│   │   └── builtin_checks.py    # inline CSS, missing null check, etc.
│   │
│   ├── review/
│   │   ├── prompt_builder.py    # builds LLM prompt with memory context
│   │   ├── reviewer.py          # LLM call + JSON parsing
│   │   └── ranker.py            # merge, dedupe, filter rejected, rank
│   │
│   ├── feedback/
│   │   └── collector.py         # replies, resolved, reactions → retain
│   │
│   └── db/
│       ├── models.py            # SQLAlchemy models
│       └── session.py
│
├── dashboard/
│   └── app.py                   # Streamlit: memory timeline, rules, review metrics
│
├── scripts/
│   ├── seed_demo_data.py        # loads fake PR history for the demo
│   └── run_reflect.py           # manual trigger of the reflect job
│
├── tests/
│   ├── test_diff_parser.py
│   ├── test_retrieval.py
│   ├── test_rule_promotion.py
│   └── test_end_to_end.py
│
└── demo/
    ├── sample_repo/             # small repo used to demo
    └── demo_script.md           # exact steps for live demo
```

---

## 9. Data Models (simplified)

```python
Memory:
  id, repo, type            # convention | decision | bug | feedback
  text, source_pr, author, file_pattern, language
  embedding, created_at, last_used_at
  accepted_count, rejected_count

Rule:
  id, description, check_type   # regex | ast | llm
  pattern, severity, confidence
  source_memory_ids[], status   # active | candidate | retired

FeedbackEvent:
  id, review_comment_id, memory_id, outcome   # accepted | rejected | ignored
  reviewer, timestamp
```

---

## 10. How the "Interaction 1 → 5 → 15" Story Works

**Interaction 1 (cold, generic)**
Diff contains `<div style="color:red">`. Agent says: *"Consider extracting inline styles."* Reviewer replies: *"We use Tailwind here, not inline CSS."* → **Retained** as a convention memory.

**Interaction 5 (memory recall)**
Another PR has inline style. Recall returns the earlier comment. Agent says: *"In PR #42 your team decided to avoid inline CSS in favour of Tailwind classes, and required null checks on API parameters."*

**Interaction 15 (proactive rule)**
Reflect has seen this pattern in 3+ PRs by 2+ reviewers → promoted to a **rule**. The rule engine flags it instantly, before the LLM is even called, and the agent also warns about related recurring violations (e.g., missing null checks in `api/` files).

---

## 11. Evaluation & Success Metrics

We will show these in the dashboard and demo:

| Metric | How measured | Target |
|---|---|---|
| **Repeated-comment rate** | % of comments that duplicate a past human comment | ↓ over time |
| **Review cycles per PR** | Number of review rounds before merge | ↓ |
| **Memory hit rate** | % of comments that cite a past memory | ↑ from 0% |
| **Suggestion acceptance rate** | accepted / (accepted + rejected) | ↑ |
| **Time to first useful comment** | seconds after PR opened | < 60s |

**Baseline vs ours:** Run the same set of 15 sample PRs through (a) a stateless LLM reviewer and (b) MemReview. Compare metrics side by side.

---

## 12. Setup & Run

```bash
git clone <repo-url> && cd memreview
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in keys

# 1. Seed demo memory (or import real PR history)
python scripts/seed_demo_data.py

# 2. Start server
uvicorn app.main:app --reload --port 8000

# 3. Expose webhook (for GitHub)
ngrok http 8000                  # paste URL in GitHub App webhook settings

# 4. Start dashboard
streamlit run dashboard/app.py
```

---

## 13. Team Roles (4 members, adjust as needed)

| Member | Owns | Deliverables |
|---|---|---|
| **A: Integration** | `github/`, `api/webhook.py`, deployment | Webhook works, comments post to PR, bootstrap import |
| **B: Memory** | `memory/` (retain, recall, reflect) | Hybrid retrieval, rule promotion, decay |
| **C: Review Engine** | `parsing/`, `rules/`, `review/` | Diff parser, prompt builder, ranker |
| **D: Frontend & Demo** | `dashboard/`, `demo/`, `tests/`, slides | Dashboard, demo script, metrics, README polish |

**Suggested timeline**

| Phase | Work |
|---|---|
| Hour 0–4 | Setup repo, webhook, fetch diff, post a hardcoded comment |
| Hour 4–10 | Memory retain/recall working, LLM review with recalled context |
| Hour 10–16 | Feedback capture + reflect job + rule engine |
| Hour 16–20 | Dashboard, seed data, metrics |
| Hour 20–24 | Testing, demo rehearsal, slides |

---

## 14. Demo Script (3–4 minutes)

1. **Show the problem:** a normal LLM reviewer gives generic feedback and forgets everything.
2. **PR #1:** open a PR with inline CSS → generic comment → reviewer corrects it → show memory saved in the dashboard.
3. **PR #5:** similar mistake → agent cites PR #42 and the Tailwind + null-check decision.
4. **PR #15:** agent auto-flags the violation via a promoted rule, and dashboard shows the rule with its confidence.
5. **Show metrics:** repeated comments down, memory hit rate up.

---

## 15. Likely Mentor Questions & Answers

**Q: How is this different from GitHub Copilot review or CodeRabbit?**
Those mostly review each PR statelessly or with static config files. MemReview learns from your team's actual review history and feedback, and improves automatically without someone writing rules by hand.

**Q: Why not just put the rules in a config file or the prompt?**
Nobody maintains those files, and rules change. Our system discovers rules from real behaviour, tracks confidence, and retires outdated ones.

**Q: What exactly is "memory" here? Isn't it just a vector database?**
A vector DB is only the storage. Memory here also includes types (convention, decision, bug, feedback), metadata, outcome tracking, recency weighting, conflict handling, and consolidation into rules through Reflect.

**Q: How does it avoid making up citations?**
The LLM can only cite memory IDs we passed into the prompt. We validate that every cited ID exists and drop any comment that cites an unknown one.

**Q: What if two past decisions conflict?**
Conflict resolution prefers the newer and higher-confidence memory, and flags the conflict on the dashboard for a human to confirm.

**Q: What if the team changes its convention?**
Recency decay and rejection feedback lower the old rule's confidence; when it drops below the threshold, it is retired.

**Q: How do you handle a bad or noisy memory?**
Confidence scoring with Laplace smoothing, a minimum-occurrence threshold before promoting anything to a rule, and human 👎 feedback that directly reduces confidence.

**Q: How does the cold-start problem work?**
We bootstrap from historical closed PRs and their review comments via the GitHub API, so the agent is useful from day one.

**Q: How do you keep it from spamming comments?**
The ranker caps comments per PR, dedupes similar ones, filters anything previously rejected, and prioritizes by severity × confidence.

**Q: How do you measure that it actually works?**
Baseline vs MemReview on the same PR set, tracking repeated-comment rate, review cycles, memory hit rate, and acceptance rate (see §11).

**Q: Privacy and security concerns?**
Memory is scoped per repo/org. Webhooks are verified with a secret. Code is sent to the LLM only as diff hunks. For sensitive teams, a self-hosted LLM can replace the API model.

**Q: Does it scale?**
Retrieval is per hunk with metadata filters and top-k limits; reflect runs as an async scheduled job. For larger orgs: Postgres + pgvector and a task queue.

**Q: Which languages does it support?**
Any language for LLM review; AST-based rules for languages with tree-sitter grammars (we start with JavaScript/TypeScript/Python).

**Q: What are the limitations?**
Quality depends on the quality of past review comments; needs some history to shine; LLM can still make mistakes, so it acts as an assistant and not a merge gate.

---

## 16. Future Scope

- GitLab and Bitbucket support
- Slack/Jira context as extra memory sources
- Per-team and per-developer memory scopes
- Auto-generated `CONTRIBUTING.md` from learned rules
- Auto-fix suggestions as commit suggestions
- CI integration to block merges on high-confidence rule violations

---

## 17. Glossary

- **Hunk:** a contiguous changed block in a diff.
- **RAG:** Retrieval-Augmented Generation, where retrieved context is added to the LLM prompt.
- **RRF:** Reciprocal Rank Fusion, a method to merge ranked lists from different search methods.
- **AST:** Abstract Syntax Tree, the structured representation of code.
- **Reflect:** consolidating raw memories into higher-level knowledge (rules).

---

## 18. Team

| Name | Role |
|---|---|
| Lahari| Integration |
| Hansika Devi| Memory |
| Yasasri | Review Engine |
| Jyothi| Frontend & Demo |
