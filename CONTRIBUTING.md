# Contributing

Thanks for contributing to ClawInboxRAG.

## Scope

This repository focuses on a safe, portable community skill layer for local `gmail-rag` workflows.

## Workflow

1. Create a focused branch.
2. Keep changes small and practical.
3. Update docs when behavior changes (`SKILL.md`, `references/`, `README.md`).
4. Run a quick local sanity check:

```bash
python3 scripts/parse_mail.py "mail status"
python3 scripts/parse_mail.py "mail from:alice@example.com max 5"
```

## Style

- Prefer clear, explicit command behavior over clever parsing.
- Preserve safety constraints (read-only access, bounded outputs, no secret leakage).
- Avoid hardcoded machine-specific paths or identities.

## Pull Requests

- Explain what changed and why.
- Include before/after examples for parser or command behavior changes.
- Ensure no docs contradict current script behavior.
