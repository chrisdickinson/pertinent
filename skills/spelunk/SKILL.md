---
name: spelunk
description: Kick off an investigation or continue one in process. Consult evidence already collected, identify sources, seek to build context the user can use, and store that information in Trivia in a structured fashion.
---

# Spelunk

**Core principle**: act as a librarian and research assistant. Investigate
sources, surface facts that *seem relevant* to the research, store them in
a structured fashion along with citation information so they can be referenced
later.

- The user asked you to investigate or continue investigating a topic. This
  investigation may span different sources: JIRA, GitHub, Notion, the internet,
  essentially all available tools.
- You should first attempt to recall a Trivia root memory for the investigation.
  If the user hasn't given you a specific tag, search for relevant
  investigations by mnemonic.
- If no root memory with a tag exists, create a new memory and generate a tag.
- If one tag exists, use it.
- If multiple tags exist and there's no clear winner, ask the user to pick a tag.
- Perform the investigation.
  - If you can recall a memory that sufficiently covers the user's question,
    show it to them. If the memory is older than a few days, confirm with the
    memory's cited source. If the memory is outdated, rate it not useful and
    continue. If it's useful, rate it useful and stop.
  - The user will likely scope your research to one or more avenues -- Notion,
    JIRA, Slack.
  - Fan out agents to perform your work. Give the agents instructions to use
    trivia to record the results they find most relevant.
- Once the investigation is complete, perform a fast review of the recorded
  memories -- recall all by tag and then link/rate results.
- Present the user the most relevant results.

## Formats

- Root memory tag format: `spelunk/<project>`.
- Root memory mnemonic: `Core memory for <project> research`. Embellish if this lands too close to other memories.
- Agent memories should be linked to the core memory and tagged with AT LEAST
  `spelunk/<project>/`.
- Memory body: cite concrete findings. No adverbs. Drop value judgements. Be laconic.
  State just the facts as they relate to the investigation prompt. 1 sentence
  finding as lede, followed by 1-3 sentences detail. MUST have citations
  as the trailing content.
  - If there are no citations, you do not have a memory.
- Citation should be in the following format, at the end of the memory body. If
  there are multiple sources for a memory, list all of them. The URL should be
  something you can use to refetch the information.

```markdown
- [Title](URL, URN, or identifier) (<channel>; originated YYYY-MM-DDTHH:ii:ss; fetched YYYY-MM-DDTHH:ii:ss)
```

Example memory, given a prompt:

```markdown
Found evidence that `Pending` enum variant was not used by UI.

`Pending` was introduced early in project to align with a prototype
implementation, but it is not in use by the production UI.

- [Commit <sha>: introduction of Pending](https://github.com/chrisdickinson/clams/...) (Github; originated 2020-01-04T13:33:00; fetched 2025-01-03T03:30:00)
- [Slack thread: "What does pending do exactly?"](https://slack.com/<CID>/<MSGID>) (Slack; originated 2023-12-31T03:30:30; fetched 2025-01-03T03:30:00)
```
