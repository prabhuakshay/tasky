# tasky

A task manager in your terminal, built with [Textual](https://textual.textualize.io/).

> **Status:** early days. You can add todos, complete them, and archive the completed ones.

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
| `alt+a` | Archive completed todos |
| `alt+v` | Show the archive (`alt+v` again to go back) |
| `alt+u` | Restore the selected todo from the archive |
| `alt+q` | Quit |

Shortcuts work while you're typing, so you never have to leave the input to use them.

Completing a todo leaves it in the list, struck through, so you can see what you got
done and undo a mis-click. `alt+a` sweeps those into the archive once you're finished
with them. `alt+v` shows the archive, newest first; tasky only reads it when you ask for
it, so opening the app stays instant no matter how much you archive.

`alt+u` puts an archived todo back on your list, exactly as it was — still completed, so
it is a true undo of archiving. Press `enter` on it to reopen it.

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

Both are plain text, so you can read, grep, or back them up with anything.

## Development

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync          # install dependencies
uv run tasky     # run the app
```

## License

MIT — see [LICENSE](LICENSE).
