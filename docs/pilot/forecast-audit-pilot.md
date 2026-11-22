# forecast-audit pilot (owner-run; nothing here is a result)

Goal: learn whether three people outside the project can run the tool on their own data and read
the denominator correctly. **No outreach is done by the agent.** Record answers verbatim in
`docs/pilot/results.md`; never fill it with invented sessions.

## Volunteers
Three people who build or evaluate forecasts (energy, demand, operations, research). One person
who has never seen the repository.

## Script (about 30 minutes, you stay silent while they work)
1. Send only the README of `examples/forecast-audit/` and a one-line ask. Start a timer.
2. Ask them to run the quickstart. Note the time to first report and every error message.
3. Ask them to prepare two CSVs from their own data (or a toy). Note each stumble.
4. Before explaining anything, ask: "What does the report say the model covered, and out of how many?"
   Record the answer (this tests the denominator reading).
5. Ask what they would change first. Record verbatim.

## Record per volunteer
Time to first report; errors hit; denominator reading (right / wrong / unsure); first change they
asked for; would they use it again (yes / no / maybe, with reason).

## Decision rule (write it before the first session)
If two of three cannot read the denominator or need over 20 minutes for the quickstart, the next
work is documentation, not features.
