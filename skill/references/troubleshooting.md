# ClawInboxRAG troubleshooting

## `ERROR: GMAIL_RAG_REPO is not set`

- Export `GMAIL_RAG_REPO` to the backend checkout used by the skill.

## `ERROR: GMAIL_RAG_REPO does not exist`

- Verify the path is correct and readable.

## `ERROR: runner not found in PATH`

- Install `uv` or set `GMAIL_RAG_UV_BIN` to the correct executable.

## Auth failures

- Confirm the token exists at `GMAIL_TOKEN_PATH`.
- Confirm it was authorized with Gmail read-only scope.
- Re-run the local OAuth flow if the token is stale or revoked.

## Semantic or hybrid search fails

- Verify the FAISS index and metadata exist under `GMAIL_RAG_BASE`.
- Run the maintenance flow (`mail sync`) or rebuild embeddings/index explicitly.
- Fall back to keyword mode for exact-match validation.

## `labels` or `recents` fails

- Confirm the configured backend checkout actually exposes those CLI subcommands.
- Treat them as backend-dependent passthrough operations, not guaranteed wrapper-only commands.

## Empty or weak search results

- Reduce query specificity.
- Check label/date filters.
- Try keyword mode.
- Confirm the relevant message period has been ingested.

## Safety reminder

This skill is read-only and should not expose tokens or full sensitive message bodies.
