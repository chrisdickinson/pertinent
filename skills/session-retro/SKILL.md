---
name: session-retro
description: Use at the end of a working session, before final commit, when the user says "let's wrap up" / "let's retro" / "any lessons from this session", or after a meaningful unit of work just landed
---

# Session Retro

Reflect on a working session and turn the lessons into durable trivia memories. The point is the *feedback loop*: next session's first `recall` should pick up what we learned.

**Core principle:** specific lessons or none. "Be more careful" is not a lesson. "Don't reach for `Box<dyn Error>` in library APIs because we hit `?` ergonomic problems three times" is.

## When to use

- End of a session.
- Before a final commit on a meaningful chunk of work.
- After a feature lands, a bug is fixed, or an investigation concludes.
- User asks for a retro explicitly.

**Skip if:** session was trivial (one-line fix, doc tweak) or was pure exploration with no conclusion.

## Steps

### 1. Recall prior retros

```
recall(query = "retro", tags = ["project:<slug>", "retro"], limit = 3, truncate = 500)
```

The params carry the cap — `limit = 3` for the top three, `truncate` so a long body doesn't blow up context — rather than recalling five and skimming past two. Skim the results. If anything from the past applies to today's session, mention it — and `rate` those memories up if they helped, down if they were noise. Trivia ranking improves with feedback.

### 2. Summarize the session in 3–6 bullets

Plain prose, not a diff. What got done, what stalled, what surprised us. This is for the user to confirm before we commit lessons; don't memorize it.

### 3. Two columns

Walk through the session and identify:

**Worked well** — approaches, tools, patterns, framings that produced results faster or cleaner than expected. For each:

```
memorize(
  mnemonic = "<slug>/worked/<short-handle>",
  content  = "Situation: ... | What we did: ... | Why it worked: ...",
  tags     = ["project:<slug>", "retro", "worked"]
)
```

**Didn't work / friction** — dead ends, tools that fought us, framings that misled us, advice that was wrong. For each:

```
memorize(
  mnemonic = "<slug>/avoid/<short-handle>",
  content  = "Situation: ... | What we tried: ... | Why it failed: ... | What to try instead: ...",
  tags     = ["project:<slug>", "retro", "avoid"]
)
```

The `Why` field is non-negotiable. Without it the lesson can't survive contact with a different situation.

### 4. Update `current-focus`

If the session changed what you're working on next, `edit` the `<slug>/current-focus` memory rather than memorizing a new retro entry. Retros are for *durable* lessons, not state.

### 5. Confirm with the user

List the memories you saved, with their mnemonics. Ask if any should be edited or dropped before they cement.

## Anti-patterns

| Don't | Why |
|-------|------|
| Memorize the diff or session transcript | Git already has it. Trivia is for the *meaning* you extracted. |
| Memorize "currently debugging X" as a retro | That's state, not a lesson. Update `current-focus` instead. |
| Write a memory whose lesson is "be more careful" / "test more" | Too vague to ever match a future situation. Be specific or skip. |
| Save five lessons from a one-hour session | Most sessions produce 0–2 durable lessons. Quality over volume. |
| Skip the `Why` field | Without the reason, the lesson can't generalize and won't help next time. |

## Quick template

```
Worked:
  <slug>/worked/<handle>
    Situation: ...
    What we did: ...
    Why it worked: ...

Avoid:
  <slug>/avoid/<handle>
    Situation: ...
    What we tried: ...
    Why it failed: ...
    What to try instead: ...
```

## Example

```
User: let's wrap up
You: [recall("retro", tags=["project:ratatui-clock", "retro"]) → finds one prior memory about a ratatui redraw quirk]
     Today: smooth redraw is working. The fix turned out to be a single buffer.swap_buffers() at the end of each frame, not the per-widget approach we tried first.
     Lessons:
       Worked → ratatui-clock/worked/single-swap-per-frame
         Situation: flicker on full-screen redraws.
         What we did: Single buffer swap at end of frame, draw to back buffer only.
         Why it worked: ratatui's diff is per-frame; per-widget swaps fight it.
       Avoid → ratatui-clock/avoid/per-widget-redraw
         Situation: same.
         What we tried: forcing redraw on each Widget::render.
         Why it failed: ratatui already diffs internally; doubling up causes flicker.
         What to try instead: trust the framework's diff and only swap once per tick.
     Also rated the prior "ratatui frame timing" memory up — it pointed us at the buffer model.
     Save these?
User: yes
You: [memorizes both, confirms]
```
