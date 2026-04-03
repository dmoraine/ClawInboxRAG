# ClawInboxRAG security guidance

## Scope

This skill is read-only by design.

It must never:

- send mail
- delete mail
- modify mailbox state
- print OAuth tokens
- print full sensitive message bodies

## OAuth handling

- Use read-only Gmail scope only
- Keep tokens local
- Do not paste secrets into responses
- Redact any accidentally surfaced token values in user-facing text

## Output hygiene

- Return short excerpts
- Clamp result counts
- Validate date input before execution
- Prefer stable links or citations over raw content dumps
- Pass user input as separate arguments instead of interpolating shell strings

## User privacy

Return only the minimum mailbox content needed to answer the request.
