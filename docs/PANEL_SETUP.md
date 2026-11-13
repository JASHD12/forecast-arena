# Human panel setup (H06)

The human panel is optional. Invited people forecast the same questions; their median
appears as the forecaster `human_panel` when at least 3 of them answered a question.
No names or e-mail addresses ever enter the repository.

## 1. Before you invite anyone

- Decide the timing with the project's maintainers: questions appear with the morning run
  (about 05:30 UTC) and lock at 09:30 UTC. See "Open decision" at the end.
- Tell every member, in writing, what is stored: a pseudonym (`panel-` plus 8 hexadecimal
  characters derived from their token), their probabilities and the submission times. It
  is published on the public site and in the public ledger. Get their agreement.

## 2. Create the tokens (one per person)

Run once per member on your own computer:

```bash
python -c "import secrets; print(secrets.token_urlsafe(16))"
```

Send each person their token privately. Keep the list of who has which token outside the
repository (or do not keep it at all). Tokens must be 12-64 characters of letters, digits,
`-` or `_`; the command above produces such tokens.

Optional allowlist: to reject unknown tokens, compute each token's SHA-256

```bash
python -c "import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" <token>
```

and send the hashes (not the tokens) to the maintainers to add to the configuration.

## 3. Create the form

Any form tool that can publish responses as CSV works. Ask four things:

| Field (column name) | Content |
|---|---|
| `token` | the member's token |
| `question_id` | the id shown on each question page of the site |
| `probability` | a number between 0 and 1 |
| `submitted_at` | the submission time in ISO 8601 with a UTC offset, e.g. `2026-11-12T08:15:00+00:00` (most tools add a timestamp column; rename or map it) |

The published CSV must have exactly this header line:

```
token,question_id,probability,submitted_at
```

## 4. Publish the responses and connect them

1. Publish the response sheet as CSV (a public link that returns the CSV text).
2. In the GitHub repository: Settings > Secrets and variables > Actions > Variables, add
   `ARENA_PANEL_CSV_URL` with that link.
3. Tick H06 in `docs/project/HUMAN_TODO.md`.

## 5. Rules the system applies

- Submissions at or after a question's lock time are ignored.
- If someone answers the same question twice, the latest valid answer counts.
- Rows with a malformed token, a probability outside [0, 1] or an unreadable time are
  rejected and counted (the Status page will show the counts), never repaired.
- The panel forecast is the median of the members' answers when at least 3 answered.

## Open decision (for the project owner)

Today the morning run seals the batch the first time it runs (about 05:30 UTC), and that
is also when the questions appear. Panel answers given between 05:30 and the 09:30 lock
therefore cannot be added to the sealed batch. Options are listed under "Proposals" in
`docs/project/DECISIONS.md`; the panel goes live (T092) only after this is decided.
