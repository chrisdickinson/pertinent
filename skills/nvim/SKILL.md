---
name: nvim
description: Control the running Neovim instance via its RPC socket. Use when the user asks to open files, split panes, switch tabs, jump to lines, or run Ex commands in their editor.
disable-model-invocation: true
---

# Neovim Remote Control

Communicate with the user's running Neovim instance over the `$NVIM` socket using `nvim --server "$NVIM"`.

## Prerequisites

- `$NVIM` must be set (it is when Claude Code is launched from within a Neovim terminal).
- If `$NVIM` is unset or the socket is dead, tell the user and stop.

## Core Commands

### Execute an Ex command (preferred)

```bash
nvim --server "$NVIM" --remote-expr 'execute("command")'
```

**Always prefer `--remote-expr 'execute(...)'` over `--remote-send`.** The `--remote-send` approach sends keystrokes, which get swallowed by the shell if the active window is a terminal buffer in terminal mode. `--remote-expr` with `execute()` runs the command directly via the RPC API regardless of the active buffer type.

### Query state

```bash
nvim --server "$NVIM" --remote-expr 'expression'
```

Returns the result to stdout.

### Send keystrokes (fallback)

```bash
nvim --server "$NVIM" --remote-send 'keystrokes'
```

Only use `--remote-send` when you specifically need to send normal-mode keystrokes or input that isn't an Ex command. Be aware this will fail silently if the active window is a terminal buffer.

## Targeting a Specific Window Without Stealing Focus

When operating on a window that isn't the user's active window (e.g., controlling a side pane while the user types in a terminal), use `win_execute()` to avoid changing focus:

```bash
nvim --server "$NVIM" --remote-expr 'win_execute(WIN_ID, "edit +N /absolute/path")'
```

**Always prefer `win_execute(win_id, ...)` over `win_gotoid(win_id)` followed by `execute(...)`.** The `win_gotoid` approach steals focus, which is disruptive when the user is interacting with a different pane (e.g., a terminal buffer running Claude Code). Use `string(winlayout())` to discover window IDs.

## Common Operations

Translate the user's request into the appropriate command:

| Intent | Command |
|---|---|
| Open file in new tab | `--remote-expr 'execute("tabedit /absolute/path")'` |
| Open file in vertical split | `--remote-expr 'execute("vsplit /absolute/path")'` |
| Open file in horizontal split | `--remote-expr 'execute("split /absolute/path")'` |
| Open file at line N | `--remote-expr 'execute("tabedit +N /absolute/path")'` |
| Open file at line N in specific window | `--remote-expr 'win_execute(WIN_ID, "edit +N /absolute/path")'` |
| Go to line N in current buffer | `--remote-expr 'execute("N")'` |
| Switch to tab N | `--remote-expr 'execute("tabnext N")'` |
| Close current tab | `--remote-expr 'execute("tabclose")'` |
| List open buffers | `--remote-expr 'execute("ls")'` |
| List tabs and windows | `--remote-expr 'execute("tabs")'` |
| Get window layout with IDs | `--remote-expr 'string(winlayout())'` |
| Run any Ex command | `--remote-expr 'execute("the-command")'` |

## Path Handling

- Always resolve to **absolute paths** before sending to Neovim.
- If the user gives a relative path, resolve it against the current working directory.
- If a file path came from a tool result (Glob, Grep, etc.), it's already absolute — use it directly.

## Multiple Commands

Chain commands with `|` inside `execute()`:

```bash
nvim --server "$NVIM" --remote-expr 'execute("tabedit /path/to/file | 42")'
```

Or make multiple `--remote-expr` calls sequentially if ordering matters.

## Querying Before Acting

When the user's request is ambiguous (e.g., "open it in the other pane"), query state first:

- `execute("tabs")` — lists all tabs and their windows
- `execute("ls")` — lists all buffers
- `winnr()` / `winnr("$")` — current and last window numbers
- `tabpagenr()` / `tabpagenr("$")` — current and last tab numbers
- `bufname("%")` — current buffer name
- `getcwd()` — Neovim's working directory

## Error Handling

- If `--remote-send` fails, the socket may be stale. Report it to the user.
- If `--remote-expr` returns an error string (e.g., `Vim(tabedit):E...`), report the Neovim error.
- `win_execute()` with `normal` commands fails with "Can't re-enter normal mode from terminal mode" when the *current* window (not the target) is a terminal buffer. Use only Ex commands inside `win_execute()`.

## Finding the Right Target Window

The user's active window is almost always a terminal buffer (running Claude Code). Before acting, **find an appropriate non-terminal window** to target:

1. Query the layout and buffer list:

   ```bash
   nvim --server "$NVIM" --remote-expr 'string(winlayout())'
   nvim --server "$NVIM" --remote-expr 'execute("tabs")'
   ```

2. For each window ID in the layout, check if it's a terminal:

   ```bash
   nvim --server "$NVIM" --remote-expr 'getwinvar(WIN_ID, "&buftype")'
   ```

   Terminal buffers have `buftype=terminal`.
3. Prefer a non-terminal window in the same tab for splits/edits. If none exists, use `execute("tabedit ...")` to create a new tab (this works even from a terminal-focused window).
4. Use `win_execute(WIN_ID, ...)` to operate on the chosen window without stealing focus from the terminal.

---

## Cookbook

Recipes for advanced Neovim operations. All recipes use `--remote-expr` and are safe to run while the user's active window is a terminal buffer.

**Important:** The user is typically focused in a terminal pane running Claude Code. Recipes that operate on a buffer (annotations, signs, folds) must target a non-terminal window. Always discover the right window first using the steps above, then use `win_execute(WIN_ID, ...)` or target the buffer by number.

## Virtual Text Annotations

Overlay ghost text on code without modifying the file. Useful for inline commentary during code review or walkthroughs.

### Setup

Create a namespace once per session (idempotent — reuse if already created):

```bash
NS=$(nvim --server "$NVIM" --remote-expr 'nvim_create_namespace("claude")')
```

### Add annotation at end of line

```bash
nvim --server "$NVIM" --remote-expr "nvim_buf_set_extmark(BUF, $NS, LINE_0IDX, 0, {\"virt_text\": [[\"  << annotation text\", \"Comment\"]], \"virt_text_pos\": \"eol\"})"
```

- `BUF` — buffer number (from `execute("ls")` or `bufnr("filename")`)
- `LINE_0IDX` — 0-indexed line number
- `"Comment"` — highlight group; use `"DiagnosticWarn"` for warnings, `"DiagnosticError"` for errors, `"DiagnosticInfo"` for info

### Add annotation above a line

```bash
nvim --server "$NVIM" --remote-expr "nvim_buf_set_extmark(BUF, $NS, LINE_0IDX, 0, {\"virt_lines_above\": v:true, \"virt_lines\": [[[\"  annotation text\", \"Comment\"]]]})"
```

### Clear all annotations from a buffer

```bash
nvim --server "$NVIM" --remote-expr "nvim_buf_clear_namespace(BUF, $NS, 0, -1)"
```

### Clear all annotations from all buffers

```bash
nvim --server "$NVIM" --remote-expr "nvim_buf_clear_namespace(-1, $NS, 0, -1)"
```

**Always clean up annotations when done.** They persist until cleared.

## Quickfix List

Push a list of locations into Neovim's quickfix list so the user can navigate with `:cnext`/`:cprev`.

### Populate

```bash
nvim --server "$NVIM" --remote-expr 'setqflist([{"filename": "/abs/path", "lnum": 42, "text": "description"}])'
```

Multiple entries: add more dicts to the list.

### Set title (optional, after populating)

```bash
nvim --server "$NVIM" --remote-expr 'setqflist([], "a", {"title": "Claude: search results"})'
```

**Note:** the title must be set in a separate call — passing items and `{"title": ...}` together errors with `E475`.

### Open the quickfix window

```bash
nvim --server "$NVIM" --remote-expr 'execute("copen")'
```

### Close and clear

```bash
nvim --server "$NVIM" --remote-expr 'execute("cclose")'
nvim --server "$NVIM" --remote-expr 'setqflist([])'
```

## Sign Column Markers

Place gutter markers to flag lines of interest (hotspots, issues, bookmarks).

### Define sign types (once per session)

```bash
nvim --server "$NVIM" --remote-expr 'sign_define("ClaudeNote", {"text": ">>", "texthl": "DiagnosticInfo"})'
nvim --server "$NVIM" --remote-expr 'sign_define("ClaudeWarn", {"text": "!!", "texthl": "DiagnosticWarn"})'
nvim --server "$NVIM" --remote-expr 'sign_define("ClaudeError", {"text": "XX", "texthl": "DiagnosticError"})'
```

### Place a sign

```bash
nvim --server "$NVIM" --remote-expr 'sign_place(0, "claude_signs", "ClaudeNote", BUF, {"lnum": LINE})'
```

- First arg `0` = auto-assign ID
- `"claude_signs"` = sign group (for bulk removal)

### Remove all Claude signs

```bash
nvim --server "$NVIM" --remote-expr 'sign_unplace("claude_signs")'
```

### Clean up sign definitions

```bash
nvim --server "$NVIM" --remote-expr 'sign_undefine("ClaudeNote")'
nvim --server "$NVIM" --remote-expr 'sign_undefine("ClaudeWarn")'
nvim --server "$NVIM" --remote-expr 'sign_undefine("ClaudeError")'
```

## Scratch Buffers

Create an ephemeral buffer for notes, analysis, or plans — visible alongside code, no file on disk.

### Create in a vertical split

```bash
nvim --server "$NVIM" --remote-expr 'execute("vnew | setlocal buftype=nofile bufhidden=hide noswapfile filetype=markdown | file Claude\\ Notes")'
```

### Create in a specific window (no focus steal)

```bash
nvim --server "$NVIM" --remote-expr 'win_execute(WIN_ID, "enew | setlocal buftype=nofile bufhidden=hide noswapfile filetype=markdown | file Claude\\ Notes")'
```

### Write content

```bash
nvim --server "$NVIM" --remote-expr "nvim_buf_set_lines(bufnr('Claude Notes'), 0, -1, v:false, ['# Title', '', '- point one', '- point two'])"
```

### Append content

```bash
nvim --server "$NVIM" --remote-expr "nvim_buf_set_lines(bufnr('Claude Notes'), -1, -1, v:false, ['', '## New section', '- more content'])"
```

### Clean up

```bash
nvim --server "$NVIM" --remote-expr 'execute("bwipeout! Claude\\ Notes")'
```

## Diff Mode

Show two files (or a file and a scratch buffer) side by side with Neovim's diff highlighting.

### Diff two existing files in a new tab

```bash
nvim --server "$NVIM" --remote-expr 'execute("tabedit /path/to/file1 | diffthis | vsplit /path/to/file2 | diffthis")'
```

### Diff a file against scratch content (e.g., a proposed change)

```bash
nvim --server "$NVIM" --remote-expr 'execute("tabedit /path/to/original | diffthis | vnew | setlocal buftype=nofile | file Proposed\\ Change | diffthis")'
nvim --server "$NVIM" --remote-expr "nvim_buf_set_lines(bufnr('Proposed Change'), 0, -1, v:false, ['line1', 'line2', 'modified line3'])"
```

### Clean up

```bash
nvim --server "$NVIM" --remote-expr 'execute("diffoff!")'
# or close the tab entirely:
nvim --server "$NVIM" --remote-expr 'execute("tabclose")'
```

## Folding

Collapse irrelevant code so the user sees only what matters during a walkthrough.

### Fold a range

```bash
nvim --server "$NVIM" --remote-expr 'win_execute(WIN_ID, "setlocal foldmethod=manual | 5,20fold")'
```

### Open all folds

```bash
nvim --server "$NVIM" --remote-expr 'win_execute(WIN_ID, "%foldopen!")'
```

### Fold everything except a range (focus mode)

```bash
nvim --server "$NVIM" --remote-expr 'win_execute(WIN_ID, "setlocal foldmethod=manual | 1,START_MINUSfold | END_PLUS,$fold")'
```

Replace `START_MINUS` with `(target_start - 1)` and `END_PLUS` with `(target_end + 1)`.

### Clean up

Revert to the buffer's original fold method. Query first, then restore:

```bash
# Query current setting before changing:
nvim --server "$NVIM" --remote-expr 'win_execute(WIN_ID, "setlocal foldmethod?")'
# After done, restore:
nvim --server "$NVIM" --remote-expr 'win_execute(WIN_ID, "%foldopen! | setlocal foldmethod=ORIGINAL")'
```

## Cleanup Discipline

**Always clean up after yourself.** Every recipe that creates state (extmarks, signs, quickfix, scratch buffers, folds, diff mode) must be reversed when no longer needed. When combining multiple recipes in a workflow, track what was created and tear it all down at the end.
