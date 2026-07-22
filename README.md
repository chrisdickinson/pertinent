# pertinent

A Claude Code plugin (and self-hosting marketplace) of productivity and
memory skills. Some are trivia-backed: they use the trivia MCP (`recall` /
`memorize` / `edit` / `rate`) to carry durable context across sessions.

Trivia is itself a Claude Code plugin, normally run as a local MCP server over
stdio — install it for the trivia-backed skills to work. Some users point it at
their own Trivia URL instead; either way these skills just call the MCP tools.

## Install

```
/plugin marketplace add /Users/chris/projects/personal/pertinent
/plugin install pertinent@pertinent
```

(Or point `marketplace add` at the git remote once this is pushed.)

## Skills

| Skill                  | What it does                                                                 | Trivia |
| ---------------------- | --------------------------------------------------------------------------- | :----: |
| `handoff`              | Compact the current conversation into a handoff doc for a fresh agent.       |        |
| `grilling`             | Interview you relentlessly to stress-test a plan, decision, or idea.         |        |
| `grill-me`             | User-invoked entry point that runs a `grilling` session.                     |        |
| `teach`                | Stateful teaching workspace — missions, lessons, learning records, glossary. |        |
| `project-trivia-setup` | Bootstrap trivia memory for a project under the `project:<slug>` tag.        |   ✓    |
| `session-start`        | Recall a project's focus + lessons, confirm direction, plan the work.        |   ✓    |
| `session-retro`        | Turn a session's lessons into durable trivia memories.                       |   ✓    |
| `spelunk`              | Record research/investigation findings under the structured `spelunk` tag.   |   ✓    |

## Trivia conventions

The trivia-backed skills share one tag scheme so the global DB stays organized:

- `project:<slug>` — scopes memories to a repo (`project-trivia-setup`).
- `focus` / `conventions` — project state and rules (`session-start`).
- `retro` / `worked` / `avoid` — durable lessons about *how work went* (`session-retro`).
- `spelunk` — durable *findings about the subject* from research (`spelunk`).

`session-retro` writes lessons at the end of a session; `session-start` reads
them back at the beginning. `spelunk` is the sibling for research: it records
the map of the terrain, kept separate from the trip report.

## Provenance

- `handoff`, `grilling`, `grill-me`, `teach` — from [mattpocock/skills][matt] (MIT).
- `session-start`, `session-retro`, `project-trivia-setup` — from [ceejbot/ceej-skills][ceej] (MIT).
- `spelunk` — original to this plugin.

Upstream `agents/openai.yaml` files (OpenAI-runtime config) were dropped; the
`disable-model-invocation` frontmatter already conveys the same intent to
Claude Code.

## License

MIT — see [LICENSE](./LICENSE). The upstream skills are MIT-licensed by their
respective authors.

[matt]: https://github.com/mattpocock/skills
[ceej]: https://github.com/ceejbot/ceej-skills
