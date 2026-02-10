# Security Guidance

- Keep Gmail access read-only (no send/delete operations).
- Do not expose OAuth credentials, refresh tokens, or local secret paths in normal output.
- Avoid dumping full email bodies unless explicitly required and safe.
- Sanitize and bound user inputs:
  - clamp `max/top`
  - parse dates strictly
  - reject malformed options gracefully
- Prefer argument arrays/subprocess-safe invocation patterns over shell string interpolation.
- Use conservative defaults to reduce accidental data overexposure.
