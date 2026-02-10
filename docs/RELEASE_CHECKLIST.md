# ClawHub Release Checklist (Pre-Publish)

Use this checklist before publishing ClawInboxRAG to ClawHub.

## Product Readiness

- [ ] `README.md` explains value proposition, setup, usage, safety, troubleshooting, roadmap.
- [ ] `SKILL.md` is consistent with actual scripts and uses `ClawInboxRAG` naming.
- [ ] `references/` docs match parser and CLI behavior.

## Safety and Compliance

- [ ] Read-only Gmail scope is documented and enforced by policy.
- [ ] Wrapper allowlist is documented (`search`, `recents`, `status`, `labels`, `ingest-primary`, `embed`, `refresh-labels`).
- [ ] No secrets, tokens, or private local paths are committed.

## Repository Hygiene

- [ ] `LICENSE` present and correct.
- [ ] `.gitignore` covers local/env artifacts.
- [ ] `CONTRIBUTING.md` and `CHANGELOG.md` are present and current.

## Verification

- [ ] Parser sanity checks run locally.
- [ ] Internal markdown links resolve.
- [ ] Command examples are coherent with `scripts/parse_mail.py` and `scripts/run_cli.sh`.

## Publication Gate

- [ ] Version/tag decided.
- [ ] Changelog updated for release version.
- [ ] Final review complete.
- [ ] Publish action explicitly approved.

Note: This checklist is for readiness only. Do not publish automatically.
