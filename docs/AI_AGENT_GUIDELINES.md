# AI Agent Guidelines

Start here when using an AI coding agent in this project.

## Read First

- [README.md](../README.md) - project purpose, stack, setup, and dev commands.
- [docs/security.md](security.md) - security and privacy checklist.

## Project Context

This is an email generation assistant that creates professional emails based on user input using an LLM with advanced prompt engineering. It takes intent, key facts, and tone as input and produces well-written, professional emails.

Important boundaries:

- Do not send emails automatically without human review.
- Mask sensitive data before any LLM boundary.
- Keep API routes thin; put behavior in domain services.
- Prefer tests for any behavior change.

## Four Rules

### 1. Think Before Coding

- State assumptions when the task is unclear.
- Ask before guessing on risky ambiguity.
- Surface tradeoffs and simpler options.

### 2. Simplicity First

- Build only what was asked.
- Avoid speculative abstractions.
- Prefer the smallest clear change that works.

### 3. Surgical Changes

- Touch only files and lines needed for the request.
- Match existing style.
- Clean up only unused code created by your change.

### 4. Goal-Driven Execution

- Define how success will be verified.
- Prefer tests or concrete checks.
- Keep working until the requested result is verified.

## Working Pattern

1. Read the related module before editing.
2. Identify the smallest useful change.
3. Make the change.
4. Run the narrowest relevant check.
5. Report what changed and how it was verified.

## Useful Checks

```bash
uv run pytest
uv run ruff check .
uv run pyright
```

Use narrower test commands when the change is small.
