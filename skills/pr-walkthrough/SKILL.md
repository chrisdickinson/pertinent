---
name: pr-walkthrough
description: Use when the user wants to walk through a checked-out PR in Neovim, one changed file per tab, each with a primed Claude session to ask questions in. Triggers on "walk me through this PR in nvim", "open the PR files in tabs with claude sessions", "PR tour". Builds on the nvim skill.
---

# PR Walkthrough

Open the "spine" of a locally checked-out PR as Neovim tabs. Each tab has two
panes: the changed file on the left (scrolled to the change), a read-only
Claude session primed on that file on the right. The user then asks questions
in every tab at once, instead of stepping one pane set through the PR.

Requires the `nvim` skill (`$NVIM` socket). If `$NVIM` is unset or dead, say so
and stop.

## Steps

### 1. Get the changed files

Use the base the PR actually targets, with a three-dot diff so base drift
doesn't leak in:

```bash
gh pr view <n> --json baseRefName,headRefName,title,files
git diff -U0 origin/<base>...HEAD -- <path>
```

Confirm the checkout matches the PR head first.

### 2. Choose the spine

Pick the files that carry the design, ordered outside-in:

1. API contract (OpenAPI/schema, DTOs, handlers)
2. Domain types and logic
3. Storage (queries, migrations)
4. Client/UI entry points

Skip generated code (`.sqlx`, generated clients/types), snapshots, and tests
unless asked. Ask the user what they care about if it isn't clear. Each tab is
a full Claude session, so aim for ~10 or fewer; list what you left out.

### 3. Write the priming prompts

One file per tab in `/tmp/pr<n>/NN.md`. Each states: the PR (number, repo,
branch, title); that other sessions cover other files; the file and its role in
the PR; that the session is read-only; and the steps:

1. Run the three-dot diff for the file and read it; read adjacent code only as
   needed.
2. Reply in at most 3 short paragraphs: what changed, what contract it exposes
   or consumes, what deserves scrutiny.
3. Wait for questions; answer laconically, cite `file:line`.

### 4. Write one Vim script per tab

`/tmp/pr<n>/tabNN.vim`. Generate these with a script rather than inlining them
in `--remote-expr`, whose quoting breaks on the prompt text:

```vim
tabedit /abs/path/to/file
vsplit
wincmd l
enew
call termopen(['claude','--permission-mode','plan',join(readfile('/tmp/pr<n>/NN.md'),"\n")],{'cwd':'/abs/repo'})
let t:pr<n> = 'NN'
```

`termopen` with a list avoids shell quoting. Plan mode keeps the sessions
read-only.

### 5. Open the tabs

Open one first and check the layout (`execute("tabs")`,
`string(winlayout())`). Then source the rest:

```bash
nvim --server "$NVIM" --remote-expr 'execute("source /tmp/pr<n>/tabNN.vim")'
```

Each `claude` launch is slow; opening ten can take longer than the shell's 120s
timeout and nvim will not answer RPC in the meantime. If a call hangs, check
`tabpagenr("$")` with `timeout 10` before concluding it is stuck or reaching
for anything destructive. Never send keystrokes blind to a possibly modal
prompt.

### 6. Scroll each file window to its change

Files opened at line 1 are not a walkthrough. For each modified (not newly
added) file, find the hunk to start on (largest added hunk by default) and
scroll the left window there. Ex commands only, no `normal`:

```bash
nvim --server "$NVIM" --remote-expr \
  "win_execute(win_getid(1, TAB), 'call cursor(L,1) | call winrestview({\"topline\": L - 2})')"
```

New files start at line 1. Verify with `line('.', win_getid(1, TAB))` and
`getwininfo(...)[0].topline`. Say which heuristic picked each line; it is a
guess, not a reading of the code.

### 7. Hand back

Return to tab 1 (`tabfirst`). Report a table of tab → file → line, what was
left out, and where the prompts live (`/tmp/pr<n>/`) so tabs can be reopened.

## Cleanup

Tabs and terminals are the user's to close. Leave `/tmp/pr<n>/` in place for
reopening; do not `rm` with a variable path.
