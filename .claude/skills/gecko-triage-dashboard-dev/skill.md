---
name: gecko-triage-dashboard-dev
description: Mandatory dev loop for every code change in gecko-triage-dashboard. Run at the start of every implementation task.
---

# gecko-triage-dashboard Dev Loop

The **gecko-triage-dashboard Dev Loop** is a mandatory workflow for all code changes. All steps are required and cannot be skipped.

## The Cycle

Development proceeds through six sequential steps: understand the task, extract & develop, write tests, agent review, commit & push, then conclude.

## Core Requirements

- All new or changed logic must be extracted into **pure/testable functions** (no I/O, no network calls) so they can be unit tested directly.
- Every function added or changed must have **unit tests** covering its branches. If behavior is removed, a test must assert the removal holds.
- **`uv run pytest tests/unit/` must pass** before committing. Failing tests are a hard blocker — fix them, do not work around them.
- **README.md must be updated** whenever a command is added/removed or a flag/default changes.
- Unit tests go in `tests/unit/`, mock all I/O and network calls.
- Integration tests go in `tests/integration/` (only for changes touching real I/O or APIs).
- Write the failing test first — confirm it fails before implementing.
- Run `uv run ruff format` and `uv run ruff check` before committing.
- The site is public. Fixtures and published data hold no real PII: no email addresses, no real names beyond what the page must show. Restricted (non-empty `groups`) bugs never enter the data.
- No emoji. No dash used as an aside in prose.

## Process Details

### Step 1 — Understand
Read the relevant source files before touching anything. Understand the existing structure: which functions are involved, what tests already cover them.

### Step 2 — Extract & Develop
Write the implementation. Extract logic into named pure functions first, then call them from handlers/controllers. Keep entry points thin — they only wire up I/O and call pure functions.

### Step 3 — Write Tests
For every function added or changed, write unit tests:
- Happy path
- Each meaningful branch or flag
- Regression guards for removed behavior

Run and confirm green:
```
uv run pytest tests/unit/
```

### Step 4 — Agent Review
Run `/simplify` to have a fresh-context agent review the changes for code quality, reuse, and efficiency. Apply any fixes before committing.

### Step 5 — Commit & Push
```
git commit -m "<type>: <what and why>"
git push
```
Both are required. Never commit without pushing.

### Step 6 — Conclude
Summarize: what changed, what tests were added, whether README was updated.
