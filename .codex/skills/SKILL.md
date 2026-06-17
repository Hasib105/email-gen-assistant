# Guidelines

Use these project guidelines when writing, reviewing, or refactoring code.

Full project guide: `docs/AI_AGENT_GUIDELINES.md`

## 1. Think Before Coding

- State assumptions when the task is unclear.
- Ask before guessing on risky ambiguity.
- Surface tradeoffs and simpler options.

## 2. Simplicity First

- Build only what was asked.
- Avoid speculative abstractions.
- Prefer the smallest clear change that works.

## 3. Surgical Changes

- Touch only files and lines needed for the request.
- Match existing style.
- Clean up only unused code created by your change.

## 4. Goal-Driven Execution

- Define how success will be verified.
- Prefer tests or concrete checks.
- Keep working until the requested result is verified.
