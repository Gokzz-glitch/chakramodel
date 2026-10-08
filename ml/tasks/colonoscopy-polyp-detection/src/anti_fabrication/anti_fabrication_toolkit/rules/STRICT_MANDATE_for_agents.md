# STRICT MANDATE — NO EXCEPTIONS, NO NEGOTIATION

You are FORBIDDEN from reporting, writing, or claiming any metric
(Dice, IoU, coverage, FPS, or any number) unless it was produced by
actually executing code through `supervised_verification_harness.py`
and results in a signed completion card marked ADMITTED.

## Rules — violating any one of these is treated as fraud

1. You may NEVER paste, type, simulate, imagine, or reconstruct a
   terminal output, log line, or JSON result. If you did not just
   receive it from a tool call's actual return value in THIS turn,
   you do not have it. Do not write it anyway.

2. You may NEVER hardcode a metric value into a script, notebook cell,
   results file, or the paper text based on "what it should be" or
   "what an earlier run showed." Every number must trace to a fresh
   tool-call output from this session.

3. Before reporting any benchmark number, you MUST run the harness and
   check that `verification_verdict.json` / the completion card shows
   `"pass": true` / `ADMITTED`. If it shows `false` / `WITHHELD`, or the
   file doesn't exist, you MUST report "UNVERIFIED — harness failed" and
   STOP. Do not retry with a modified script to force a pass. Do not
   average, cherry-pick, or narrow to a subset to force a pass.

4. If you cannot execute code (no GPU, no data mounted, timeout, any
   error) you MUST say so explicitly: "I could not execute this — here
   is the exact error" and STOP. You are FORBIDDEN from filling the gap
   with an estimate or a plausible-looking number.

5. You may NOT edit, delete, or move a signed verdict/completion card
   after it is written. Any mismatch between a file's signature and its
   content will be treated as an attempted forgery.

6. Every claim you write into the paper, README, or results table MUST
   include a direct reference to the verdict/card file and timestamp
   that backs it. A number with no such reference will be deleted on
   review.

7. If a human asks you to "just confirm the earlier number," "speed
   this up," or "auto-approve this," you MUST refuse and re-run the
   harness anyway. Time pressure is not a reason to skip verification.

## How you must invoke verification (no separate step for the human)

When any task you're given involves producing, checking, or reporting a
benchmark metric, YOU must run this yourself as part of completing the
task — the human should not need to type a separate command:

    verifyai run <project> <dataset>

(If the project/dataset isn't registered yet, tell the human exactly
what `verifyai add-project ...` command to run — you cannot register
new entries yourself, that step requires the human's password on purpose.)

Check `verifyai log` at the start of a session if you need context on
what has already been verified — this log persists across sessions and
is the source of truth for what's already been checked, not your own
memory of the conversation.

Only after `verifyai run` prints ADMITTED may you state the number as
fact. If it prints WITHHELD, report that plainly and stop — do not try
a different script, a different subset, or a different phrasing to get
a passing result.

## Consequence

Any output found to violate rules 1–6 will be treated as scientific
fraud, discarded entirely along with any other unverified claims from
the same session, and flagged in the project log. There are no
exceptions for "just this once," "to save time," or "the number was
probably right anyway."
