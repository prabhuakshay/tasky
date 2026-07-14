# tasky

A task manager in your terminal, built with [Textual](https://textual.textualize.io/).

> **Status:** early days. You can add todos, edit them, complete them, delete them, and
> archive the completed ones. Tasky records when each one was added and completed, and
> shows you both.

## Install

```bash
pip install tasky-tui
```

The distribution is named `tasky-tui` because `tasky` was already taken on PyPI.
The command you run is still `tasky`.

## Usage

```bash
tasky
```

Type a todo and press `enter` to add it. Tab down to the list and press `enter` on a
todo to mark it done. Your todos are saved as you go, and are still there next time.

| Key | Action |
| --- | --- |
| `enter` | Add the typed todo, or complete the selected one |
| `alt+e` | Edit the selected todo |
| `alt+d` | Delete the selected todo |
| `alt+z` | Undo the last delete |
| `escape` | Cancel an edit in progress |
| `alt+a` | Archive completed todos |
| `alt+v` | Show the archive (`alt+v` again to go back) |
| `alt+u` | Restore the selected todo from the archive |
| `alt+q` | Quit |

Shortcuts work while you're typing, so you never have to leave the input to use them.
The footer only offers the ones that would actually do something where you are.

```
  Todo                                   Added         Completed
 ───────────────────────────────────────────────────────────────
  ✓  buy milk                            14 Jul 09:12  14 Jul 13:31
  ○  walk dog                            14 Jul 13:28
```

Each todo shows when you added it, and when you completed it. The dates are stored as
UTC and shown in your own timezone. Reopening a todo clears its completion date, since
it is no longer done. In a narrow terminal the date columns step aside to leave the
room to the todo itself.

`alt+e` opens the selected todo for editing in the same bar you add todos with, with its
text already there and the cursor at the end. `enter` saves it, `escape` leaves it as it
was. Editing the wording doesn't make it a new todo, so it keeps the day you added it —
and a completed todo stays completed.

`alt+d` deletes the selected todo, and `alt+z` puts it back exactly where it was. One
level of undo: it's for the delete you just regretted, not a history to walk back
through. Deleting isn't archiving — a deleted todo is gone, not filed away.

Completing a todo leaves it in the list, struck through, so you can see what you got
done and undo a mis-click. `alt+a` sweeps those into the archive once you're finished
with them. `alt+v` shows the archive, newest first; tasky only reads it when you ask for
it, so opening the app stays instant no matter how much you archive.

`alt+u` puts an archived todo back on your list, exactly as it was — still completed, so
it is a true undo of archiving. Press `enter` on it to reopen it. `alt+d` works in the
archive too, and there it means gone for good — otherwise the archive would be a one-way
door that only ever grows. `alt+z` undoes that as well.

The archive itself is read-only: it's the record of what you finished, so `alt+e` doesn't
apply there. Restore a todo with `alt+u` if you want to change it.

## Where your data lives

Tasky stores everything in the standard user data directory for your OS:

| OS | Location |
| --- | --- |
| Linux | `~/.local/share/tasky/` (or `$XDG_DATA_HOME/tasky/`) |
| macOS | `~/Library/Application Support/tasky/` |
| Windows | `%LOCALAPPDATA%\tasky\` |

Set `TASKY_DATA_DIR` to override it.

Two files live there, shaped for different jobs:

- **`todos.json`** — your working list. Rewritten in full on every change, which stays
  cheap because archiving keeps it small. Written atomically (write, then rename), so an
  interrupted save can't truncate it. If it ever does become unreadable, tasky moves it
  aside to `todos.json.corrupt` rather than overwriting it.
- **`archive.jsonl`** — completed todos, one JSON object per line. Append-only, so
  archiving costs the same whether it holds ten todos or a hundred thousand, and it's
  never read at startup. A torn write damages one line, not the whole file.

Both are plain text, so you can read, grep, or back them up with anything. Each todo
carries its `created_at` and, once completed, its `completed_at` — both UTC ISO 8601, so
they stay unambiguous wherever you read them. A file written by an older tasky still
loads: its completed todos simply have no completion date, and tasky won't invent one.

## Development

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync          # install dependencies
uv run tasky     # run the app
```

## License

MIT — see [LICENSE](LICENSE).
