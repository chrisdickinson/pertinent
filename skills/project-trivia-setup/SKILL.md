---
name: project-trivia-setup
description: Use when starting trivia memory in a Rust project for the first time, when the user says "set up trivia" or "bootstrap project memory", or when no `project:<slug>`-tagged memories exist yet for this repo
---

# Project Trivia Setup

Bootstrap the trivia MCP for a Rust project so that future sessions can recall what this project is, what's being worked on, and what conventions it follows — without polluting the global trivia DB shared across all projects.

**Core principle:** every memory belonging to a project carries the tag `project:<slug>`. Recall by tag, memorize with the tag, and the global DB stays organized.

## When to use

- New project, first time using trivia for it.
- Existing project where memories were never set up under the tag convention.
- User asks to "set up trivia" / "bootstrap project memory" / "remember this project".

**Skip if:** the sentinel memory `<slug>/trivia-bootstrapped` already exists (run `recall` for that exact mnemonic first). In that case, list what's already there and stop.

## Steps

### 1. Derive the project slug

In order:
1. Read `Cargo.toml` and use `[package].name` (lowercase, hyphens already canonical).
2. If no `Cargo.toml`, use the basename of the working directory, lowercased, with non-alphanumerics replaced by hyphens.

The slug becomes the project tag: `project:<slug>`.

### 2. Check for an existing bootstrap

```
recall("<slug>/trivia-bootstrapped")
```

If that returns a hit, **stop**. Surface the existing seed memories to the user instead of overwriting them. Offer to update individual memories, not re-run bootstrap.

### 3. Seed the initial memories

Ask the user (or infer from `README.md` / `Cargo.toml` / recent git activity if obvious) for these three facts. Memorize each one with tags `project:<slug>` plus the topical tag in the table:

| Mnemonic | Topical tag | Content |
|---|---|---|
| `<slug>/overview` | `overview` | One paragraph: what this project is and why it exists. |
| `<slug>/current-focus` | `focus` | One paragraph: what the user is working on right now. |
| `<slug>/conventions` | `conventions` | Any non-obvious project rules: build commands, MSRV, lint config, style choices, layout decisions. |

Only memorize facts the user has stated or that are unambiguous from the repo. Do not invent.

### 4. Drop the sentinel

```
memorize(
  mnemonic = "<slug>/trivia-bootstrapped",
  content  = "Trivia bootstrap completed for <slug> on <YYYY-MM-DD>. Project tag: project:<slug>.",
  tags     = ["project:<slug>", "meta"]
)
```

Future sessions detect this in step 2 and avoid re-running.

### 5. Document the convention in `CLAUDE.md`

Append (or create) a short section in the project's `CLAUDE.md`:

```markdown
## Project memory

This project uses the trivia MCP. All memories are tagged `project:<slug>`. Recall by that tag at the start of work. Add new lessons via the `session-retro` skill.
```

This makes the convention discoverable to future sessions even if the trivia tag itself ever drifts.

### 6. Report back

Tell the user:
- The slug used and where it came from (Cargo.toml vs directory).
- Each memory you created (mnemonic + one-line summary).
- That subsequent sessions should `recall("project:<slug>")` to load context.

## Anti-patterns

| Don't | Why |
|---|---|
| Overwrite an existing bootstrap | The sentinel exists for a reason — past sessions have refined those memories. |
| Seed speculative memories | Every memory should be a fact the user has stated or that's unambiguous from the repo. Speculation pollutes recall. |
| Store secrets, tokens, or private credentials | The trivia DB is global to your machine and easy to export. Treat it like a public README. |
| Use a different tag scheme per project | The `project:<slug>` convention is the whole point. Stick to it. |

## Example

```
User: set up trivia for this project
You: [reads Cargo.toml, finds name = "ratatui-clock"]
     Slug: ratatui-clock. Tag: project:ratatui-clock.
     [recall("ratatui-clock/trivia-bootstrapped") → no results, proceeding]
     What's the one-line description of this project? What are you working on right now?
User: It's a small terminal clock built on ratatui to teach myself the framework. Right now I'm trying to get smooth redraw without flicker.
You: [memorizes ratatui-clock/overview, ratatui-clock/current-focus, ratatui-clock/conventions (from Cargo.toml: edition 2021, MSRV 1.74)]
     [memorizes sentinel ratatui-clock/trivia-bootstrapped]
     [appends "Project memory" section to CLAUDE.md]
     Done. Three memories seeded under project:ratatui-clock. Future sessions can recall("project:ratatui-clock") to reload.
```
