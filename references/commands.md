# Commands

## Search

Pattern:

```text
mail <query> [keyword|semantic|hybrid] [max N|top N] [label <prefix>] [after <date>] [before <date>] [between <date> and <date>] [resume]
```

Date formats accepted:

- `YYYY`
- `MM/YYYY`
- `YYYY-MM`
- `YYYY-MM-DD`

`between` expands to inclusive month/year windows and day-inclusive ranges.

## Operational commands

- `mail help`
- `mail recents [max N|top N|limit N]`
- `mail status`
- `mail labels`
- `mail sync`

## Output style

For search results, return:

1. Date
2. Sender
3. Subject
4. Short snippet
5. Permalink/reference
