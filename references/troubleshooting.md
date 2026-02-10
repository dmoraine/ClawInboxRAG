# Troubleshooting

## `ModuleNotFoundError: gmail_rag`

- Verify repository path and virtual environment setup.
- Confirm command is executed from the configured repository.

## OAuth/auth failures

- Confirm token exists and has valid Gmail read-only scopes.
- Re-authenticate if token is expired/revoked.

## Empty semantic results

- Check embedding pipeline status.
- Run ingest/embed maintenance (`mail sync`) and retry.

## Slow responses

- Reduce result limits.
- Use keyword mode for quick exact-match checks.
- Perform periodic index maintenance.
