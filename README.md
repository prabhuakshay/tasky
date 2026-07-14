# tasky

A task manager in your terminal, built with [Textual](https://textual.textualize.io/).

> **Status:** early days. You can add todos, edit them, complete them, delete them,
> archive the completed ones, keep notes against any of them, and file them under
> projects. Tasky records when each one was added and completed, and shows you both.

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
| `enter` | Add the typed todo, complete the selected one, or show the selected project |
| `alt+e` | Edit the selected todo — or the selected note or project, in its pane |
| `alt+d` | Delete the selected todo — or the selected note or project, in its pane |
| `alt+z` | Undo the last delete, of whichever you just deleted |
| `alt+m` | Move the selected todo to a project |
| `alt+n` | Step into the notes drawer |
| `alt+p` | Step into the projects pane |
| `escape` | Cancel an edit in progress, or leave the pane you're in |
| `alt+a` | Archive completed todos |
| `alt+v` | Show the archive (`alt+v` again to go back) |
| `alt+u` | Restore the selected todo from the archive |
| `alt+q` | Quit |

Shortcuts work while you're typing, so you never have to leave the input to use them.
The footer only offers the ones that would actually do something where you are.

```
  Projects       │  Todo                      Notes │  buy milk
 ────────────────┤ ─────────────────────────────────┤ ─────────────────────────────
  Add a project  │  What needs doing?               │  Add a note
                 │
  All         3  │  ✓  buy milk  #groceries     ✎ 2 │   oat, not soya
  groceries   1  │  ○  walk dog                     │   14 Jul 09:14
  health      1  │  ○  book dentist  #health    ✎ 1 │
                 │                                  │   the corner shop stocks it
                 │                                  │   14 Jul 09:15 · edited 17:02
  2 projects     │  2 active · 1 completed          │  2 notes
```

The pane you're standing in is the one that's lit — its edge and its heading — so the
keys, which mean the thing in front of you, always have somewhere obvious to point.

Each todo shows when you added it and when you completed it (in a wider terminal than
this one — see below). The dates are stored as UTC and shown in your own timezone.
Reopening a todo clears its completion date, since it is no longer done.

## Projects

A todo can be filed under a project, and most of them never are. Filing is something
you do when it helps, not a toll you pay on the way in — so a tasky with no projects in
it is the tasky that was here before, one pane fewer, every key meaning what it always
did.

The way in is the bar you're already typing in. If the last word of a todo starts with a
`#`, that word is the project it goes in:

```
buy milk #groceries
```

The project is made the first time you name it, so there's no step between deciding to
file something and having somewhere to file it. `#Groceries` and `#groceries` are one
project, not two.

Only the last word counts, and that's the whole rule. `pay invoice #123 to acme` is a
todo about an invoice and nothing else, because the hash isn't at the end — so a todo
that has to carry a hash word has somewhere to put it. `pay invoice #123` does file
itself under a project called `123`, which is the price of a rule you can hold in your
head. It isn't a trap: the project is written on the row, `alt+e` hands you back the
very line you typed, and deleting the tag takes the todo back out again.

That round trip is what makes the tag the whole truth. What's in the bar is what the
todo is: no tag means no project, whether you never typed one or you've just rubbed it
out. Nothing is remembered behind your back.

`alt+m` is the other door, for when the todo is already there and the project is an
afterthought — which is most of the time. It opens the same bar on the same todo with
the tag started for you, so naming a project is a word and an `enter` rather than a trip
to the end of a line you didn't want to edit. It starts the tag fresh rather than
filling in the one that's there, so `enter` on the bare `#` takes the todo out of its
project: the "nowhere" answer is a keystroke, not nine backspaces.

`alt+p` steps into the pane, and lands you on the projects rather than in its bar —
you're rarely here to make one, since there's a project on the end of every todo you
type. You're here to stand in one. `enter` shows a project's todos and hands the focus
back to the list, because choosing a project is something you do on the way to working
in it. The first row is `All`, which is not a project but the way back out of one.

Standing in a project, the list *is* that project: a todo you add joins it without being
told to, `alt+a` archives the completed todos of that project and leaves the ones you
can't see alone, and the `#tag` comes off the rows — it would only repeat the same word
down the screen, and the pane and the title say it once already. Edit a todo out of the
project you're standing in and it leaves the list, because a project you're standing in
is a place, not a suggestion.

In the pane, the keys you know mean the project in front of you: `alt+e` renames it —
once, everywhere, since the todos point at it rather than spell it — `alt+d` deletes it,
and `alt+z` puts it back with the todos it held. Deleting a project isn't deleting its
todos; they go on existing, simply filed nowhere. That's what makes it safe, and `alt+d`
on the todos themselves is right there if throwing them away is what you meant.

A project name is one word, so that you can always type it as a tag. A project outlives
the todos in it: archive the last one and the project is still there to add to. That's
the whole reason a project is a thing in its own right rather than a word written on a
todo — and the reason a rename is one edit instead of one per todo.

The archive can be read a project at a time, which is much of what an archive is for.
Your projects themselves are read-only in there: rearranging them from inside a record
of what happened is not a thing to want.

## Notes

A todo is one line, and sometimes one line isn't enough. The drawer on the right holds
as many notes as you like against the todo you're on, and it follows the highlight — so
you can run down your list and read what you wrote about each one, without opening
anything.

`alt+n` steps across into it. Type a note and press `enter` to add it. `alt+e` (or
`enter` on the note itself) opens it for editing, `alt+d` deletes it, and `alt+z` puts a
deleted one back where it was. `escape` backs out of an edit; press it again to go back
to the list. `tab` moves between the two panes.

Those are the keys you already know from the list, and in the drawer they mean the note
in front of you rather than the todo it belongs to. Which pane you're standing in is
what decides — the footer changes as you move, so it always shows what the keys will do
where you are. The `Notes` column on the todo list shows which todos have something
written against them.

Each note records when it was written, and when it was last rewritten. The `edited`
half of that line only appears once you've actually changed it, so "written and never
touched since" is something you can see at a glance.

Notes belong to their todo. Archive the todo and the notes go with it; delete it and
they go too, with nothing orphaned behind. Notes on an archived todo can be read but not
changed — like the archived todo itself, they're a record of what happened. `alt+u` the
todo back to your list if you want to write more.

Four things want the width, and they give way in that order. The todo itself always gets
it. Then the notes drawer, which is about the todo you're standing on, and so the pane
worth having open while you read down the list. Then the projects pane. The dates are
the first to step aside and the last to come back: they're a record and the todo is the
point — and they're the only one of the four you can't ask for, since `alt+n` and
`alt+p` fetch a pane wherever you're standing, and a todo wears its project on its own
row.

A terminal of about 130 columns holds all four. Narrower than that, the dates step aside
for the panes; they're still in the file, and still there when you widen the window.
Narrower than 100, the projects pane stops standing beside the list, and narrower than
60 the notes drawer does too. A pane that can't stand beside the list isn't gone:
`alt+n` and `alt+p` put it in front of the list instead, and `escape` gives the list
back. So the notes and the projects are reachable in any terminal; they just can't
always be read at the same time as the todos they belong to.

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

Three files live there, shaped for different jobs:

- **`todos.json`** — your working list. Rewritten in full on every change, which stays
  cheap because archiving keeps it small. Written atomically (write, then rename), so an
  interrupted save can't truncate it. If it ever does become unreadable, tasky moves it
  aside to `todos.json.corrupt` rather than overwriting it.
- **`archive.jsonl`** — completed todos, one JSON object per line. Append-only, so
  archiving costs the same whether it holds ten todos or a hundred thousand, and it's
  never read at startup. A torn write damages one line, not the whole file.
- **`projects.json`** — the projects you file todos under. A file of their own, because
  a project outlives the todos in it, and neither of the files above could hold one: the
  working list is the wrong place for something that survives the list emptying, and
  `archive.jsonl` is append-only, so nothing in it could ever be renamed. Written only
  when the projects themselves change, which is rarely.

All three are plain text, so you can read, grep, or back them up with anything. Each todo
carries its `created_at` and, once completed, its `completed_at` — both UTC ISO 8601, so
they stay unambiguous wherever you read them.

Its notes are nested inside it, each with its own `created_at` and, once edited, its
`updated_at`; that's what makes archiving a todo carry its notes along for free, and
deleting one take them with it. Its project is the other way about — named by `id`
rather than nested, because it's one project and many todos, and because it goes on
existing when the todos in it don't.

That does mean an archived todo can name a project you've since deleted. It shows no
project, which is the truth: there's no longer one to show. Deleting a project unfiles
the todos still in your list, but it doesn't reach back into the archive and rewrite what
happened.

A file written by an older tasky still loads: its completed todos simply have no
completion date, its todos have no notes and are in no project, and tasky won't invent
any of it.

## Development

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync          # install dependencies
uv run tasky     # run the app
```

## License

MIT — see [LICENSE](LICENSE).
