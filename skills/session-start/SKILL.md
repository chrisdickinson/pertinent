---
name: session-start
description: Use at the start of a working session, when the user says "let's get started" / "what were we working on" / "let's pick this back up", or before beginning a meaningful chunk of work. Recalls the project's current focus and most relevant lessons from trivia, confirms direction, and enters plan mode to design the work.
---

# Session Start

Open a working session by consulting what we already know and planning before we
act. This is the other half of the `session-retro` loop: retro _writes_ the
current focus and durable lessons at session end; start _reads_ them back at the
beginning so they shape the work from the jump.

**Core principle:** load the _few most important_ memories, not everything tagged
`project:<slug>`. Recall is curated and capped. The goal is to walk into the
session reminded of what matters — not to drag the whole project history into
context.

## When to use

- The start of a session, before real work begins.
- Picking work back up after time away ("what were we working on?").
- Before a meaningful chunk of work, when a plan would help.

**Skip if:** the ask is a trivial one-off (a quick lookup, a one-line fix), or
the user already knows exactly what they want and explicitly wants to dive
straight in.

## Steps

### 1. Derive the project slug

If $0 is provided, use this as the project slug. If it isn't provided, derive the
project slug using the same convention as `project-trivia-setup`: read `Cargo.toml`
and use `[package].name`; if there's no manifest, use the working-directory basename,
lowercased with non-alphanumerics replaced by hyphens. The slug becomes the tag
`project:<slug>`.

### 2. Check that trivia is bootstrapped

```
recall("<slug>/trivia-bootstrapped", limit = 1)
```

An existence check — `limit = 1` answers the yes/no without pulling five full
bodies into context. If there's **no hit**, this project has no memory yet.
Don't fabricate context — suggest running the `project-trivia-setup` skill
first, then stop.

### 3. Recall the focus — tightly

Pull the state and conventions directly:

```
recall(query = "current focus", tags = ["project:<slug>", "focus"],       limit = 1)
recall(query = "conventions",   tags = ["project:<slug>", "conventions"], limit = 1)
```

One focus and one conventions memory per project, so `limit = 1` gets exactly
those without four also-rans each.

Then a *single* lessons recall, keyed on the focus text so trivia's semantic
ranking surfaces the relevant ones. The params carry the cap: `limit = 3` for
the top three, `truncate` so a long body doesn't blow up context.

```
recall(query = "<the current-focus text>", tags = ["project:<slug>", "retro"], limit = 3, truncate = 500)
```

Let the params cap it — recalling five and trimming after pays for bodies you
throw away. And do **not** run a tag-wildcard dump like
`recall(tags = ["project:<slug>"])` — that's loading the universe, and it buries
the lessons that actually matter today.

### 4. Confirm the focus with the user

Summarize the recalled focus in one or two plain sentences, and surface any
retro lesson that bears on it ("last time we learned X"). Then ask: **is this
what you want to work on this session?**

- If the user redirects to something else, re-run the step-3 lessons recall
  against the _new_ focus before planning.
- If the focus reads as stale, say so and offer to update `<slug>/current-focus`
  via `edit` (the way `session-retro` does). Updating is optional here — this
  skill's job is to read and plan, not to rewrite memory.

### 5. Rate what helped

Same feedback discipline as `session-retro` step 1: `rate` the recalled memories
up if they shaped the direction, down if they were noise. This keeps ranking
honest, which is what makes the top-3 cap meaningful next time.

### 6. Enter plan mode and plan

Call the `EnterPlanMode` tool, then produce a plan for the confirmed focus that
**explicitly carries the recalled lessons forward** — e.g. "we hit Y last time,
so the plan avoids it by doing Z." This is the payoff: the lessons inform the
design before any code is written.

## Anti-patterns

| Don't                                            | Why                                                                                                                              |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| `recall` everything tagged `project:<slug>`      | That's the universe. Load the curated few keyed on today's focus.                                                                |
| Plan against a stale focus without confirming    | The point of step 4 is to verify direction before investing in a plan.                                                           |
| Start editing files before entering plan mode    | Defeats "plan from the jump." Confirm, then `EnterPlanMode`, then act.                                                           |
| Re-seed memories or write a retro here           | That's `project-trivia-setup` / `session-retro`'s job. This skill only reads (plus `rate` and an optional `current-focus` edit). |
| Fabricate context when trivia isn't bootstrapped | No memory means no recall. Point at `project-trivia-setup` and stop.                                                             |

## Example

```
User: what were we working on?
You: [recall("ratatui-clock/trivia-bootstrapped", limit=1) → hit]
     [recall focus (limit=1) → "smooth redraw without flicker"; recall conventions (limit=1) → edition 2021, MSRV 1.74]
     [recall("smooth redraw without flicker", tags=["project:ratatui-clock","retro"], limit=3, truncate=500)
        → top hit: ratatui-clock/worked/single-swap-per-frame]
     Last session you landed flicker-free redraw with a single buffer swap per frame, and
     the lesson saved was: trust ratatui's per-frame diff, swap once per tick. Current focus
     is still smooth redraw — want to keep going on that this session?
User: yes, I want to add a second pane and make sure it doesn't reintroduce flicker.
You: [rate single-swap-per-frame up — it's directly relevant]
     [EnterPlanMode]
     Plan: add the second pane drawing into the same back buffer, keep the single end-of-frame
     swap (per the saved lesson — don't add a per-pane swap), then verify no flicker on resize.
```
