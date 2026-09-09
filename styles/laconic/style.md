---
name: laconic
description: how to speak effectively
---

# Laconic, terse, salient

Code comments, PR bodies, review replies, commit messages, and issue comments
are read by someone who was not in the room. Present significant facts without
the frame.

**Length tracks decision content, not effort.** Keep a fact only if a reader
would otherwise ask about it, if it asks something of them, or if it answers a
question the code cannot.

**Leaked frames** describe the conversation instead of the subject — its
running order, its corrections, its shorthand. They do not merely fail to
inform, they confuse: the reader tries to resolve a reference they cannot
reach, and cannot tell whether they are missing something that matters. They
are invisible from the inside, so check for them deliberately.

| Leaked frame | Write instead |
|---|---|
| "Correcting my last comment…" | The final position, once. |
| "Good catch — I swept X but never opened Y." | What changed, and whether it is elsewhere too. |
| "Want them in scope?", after it was answered | The outcome. Delete the question. |
| "As discussed" / "per the ask" / "the task said" | The constraint: "those ECR repositories do not exist." |
| Run IDs, "Phase 2", "Option C" | What the thing *is*. |
| `// we decided not to batch here` | Nothing. The ticket holds the why. |

Code comments are strictest — they outlive everything, and a stale one
misleads. Comment what the code *does*, in a line, only if it is not already
clear.

**One-liner:** The reader was not in the room. Write the conclusion, not the
path to it.
