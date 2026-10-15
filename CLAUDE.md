# Context for Claude Code

## What this is

`signal-outbound` turns buying signals into first lines for outreach emails,
and rejects any line containing a number or name not present in the source.

## Non-negotiables

1. **The fact guard is never loosened to make output pass.** If a real line is
   rejected, fix the writer or the copy, not the guard. Add to `COMMON_CAPS`
   only for genuinely generic words.
2. **House copy contains no figures.** The guard cannot tell a sender's claim
   from a claim about the prospect. Keep numbers out of the `WHY` strings.
3. **NaiveWriter output is never exported.** It exists to demonstrate the guard.
   The CLI forces dry-run for it.
4. **Offline always.** Tests and demos need no network and no keys.
5. **Fixtures are fictional.** Never put real companies' names or news into `data/`.

## Traps already hit

- Keyword-searching for "RevOps" matched the company name "Cadence RevOps".
  Role titles are parsed from `hiring a <Title> in/to/for`.
- The guard rejected the template's own "first 90 days". Correctly.

## Commands

    make test | make demo | make naive | make again
