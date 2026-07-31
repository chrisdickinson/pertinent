---
name: establish-loops
description: Use when the user wants Claude to learn how to run and operate a repo locally, then bake that knowledge into repo-local skills. It reads the docs and task runner (including how to pass extra args to narrow a test to one file, and whether to prefer the runner or the package manager), learns how the developer runs and hot-reloads the server outside Claude, learns to observe and drive it (logs or tmux, tests, UI, backing data stores), writes `iterate`- and `cut-pr`-style skills into the repo, and adds the missing task-runner recipes. Triggers on "set up the dev loop", "learn how to run this repo", "generate iterate/cut-pr skills for this project", "map how this project runs".
allowed-tools: Bash, Read, Edit, Write, Glob, Grep, Agent
disable-model-invocation: true
---

# Establish Loops

Learn to run and operate this repo like a developer. Save what you learn as
repo-local skills. Add the task-runner recipes that are missing.

Work in the current directory. It is a code repository.

## 1. Read the repo

Read the README, `docs/`, and any `CONTRIBUTING` file.

Find the task runner: `justfile`, `package.json` scripts, `Makefile`,
`Taskfile.yml`, `Cargo.toml`, `pyproject.toml`, or `docker-compose.yml`.

Read the body of each task that runs, tests, lints, or resets. Do not guess a
command. If a command is unclear, read its definition.

Answer these:

- Does the runner wrap the package manager, or do developers call the package
  manager directly? Prefer the runner when it sets env, toolchain, or workspace
  flags. Note the cases where a raw command is expected.
- Can a task take extra arguments? Find the pass-through form, such as
  `just test <filter>`, `npm test -- <file>`, or `cargo test <name>`. Record how
  to narrow a test run to one file or one case.

## 2. Learn to run it

Assume the developer runs the server, outside Claude, for control. Do not start
it yourself unless the developer asks.

Find the start command and the dependencies the server needs: databases, queues,
object stores, and external services. Find how the server reads its config, such
as `.env` or `env.example`.

Find how the server reloads on a change. Look for a watcher: `watchexec`,
`cargo-watch`, `nodemon`, `air`, or Vite HMR. Learn what a file save triggers,
and what forces a reload by hand (a `touch`, a key, or a restart).

## 3. Learn to observe and drive it

Find the exact command for each item. Record it.

- **Output** — find where the server writes: a tmux pane, a log file, or a
  terminal. Most repos have no tmux; ask the developer where the output goes.
  For a tmux pane: `tmux capture-pane -t <pane> -p | tail -n 60`.
- **Reload** — the smallest action that reapplies a code change, per the watcher
  from step 2.
- **Tests** — the runner's test command, and the narrow-filter form from step 1.
- **UI** — drive the browser with the Playwright MCP. Read the accessibility
  snapshot first. Take a screenshot second.
- **CLI output** — capture stdout. Read it. Do not stream large output.
- **Data** — connect to each backing store read-only: `psql`, `redis-cli`, a
  kafka topic list or consume, `aws s3 ls`.

Safety: read, do not mutate. Do not print secrets or PHI. Log identifiers only.

## 4. Verify each command

Run each command once. Confirm it works before you record it. Do not record a
command that you did not run.

The developer's server may be down. Verify the read-only commands you can: tests,
data queries, and argument pass-through. Leave the server to the developer.

## 5. Write the repo-local skills

Write each skill to `.claude/skills/<name>/SKILL.md`. Use the verified commands
from steps 1–4. Match the tone of the pertinent skills: imperative and terse.
Give each skill frontmatter (`name`, `description`, `allowed-tools`).

Encode the discovered knowledge, not only the happy-path commands:

- The runner-versus-package-manager convention.
- The argument pass-through forms (narrow a test to one file or one case).
- The reload mechanism: what a save triggers, and what forces a manual reload.
- Where the server writes its output.

Skills to write:

- **`iterate`** — the dev loop: observe the server, reload, test, seed, inspect
  data, and drive the UI.
- **`cut-pr`** — the PR flow: branch, commit, push, open the PR, wait for CI,
  react to review, and merge. Use the repo's tools (`gh`, its CI recipes).

Name a skill for the repo if `iterate` or `cut-pr` does not fit. State the names
you chose.

## 6. Add the missing tasks

Compare the feedback loop against the runner's tasks. Find each step that still
needs a raw command: seed data, reset the database, tail logs, wait for healthy,
or curl with auth.

Add a recipe for each gap. Follow the repo's recipe conventions. List each new
task and the gap it closes.

## Do not

- Do not start the server unless asked; the developer runs it.
- Do not run a destructive command against real data.
- Do not print secrets or PHI.
- Do not record a command that you did not run.
