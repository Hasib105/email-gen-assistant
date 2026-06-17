# Security And Privacy

> **Status:** Draft. This is an engineering checklist, not legal approval.

## Required Defaults

- Raw PII is masked or removed before model usage.
- Placeholder maps are request-scoped unless policy explicitly approves retention.
- Logs avoid raw customer messages, raw PII, and placeholder maps.
- Secrets live in environment variables or a secrets manager, never in source.

## Production Readiness Questions

1. Which fields may reach the LLM unchanged?
2. Which fields must be placeholdered?
3. Which fields must be removed completely?
4. What is the approved model provider and region?
5. What is the retention policy for logs, traces, prompts, and completions?
