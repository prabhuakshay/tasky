"""Deleting a todo, and putting it back.

Its own file for the same reason the archive has one: it is a key's worth of behaviour
rather than part of the shape of the app, and app.py should read as the shape of the
app. Functions taking the app, again -- each one needs the whole of it, and saying so
in the signature is plainer than inheriting it and hoping.

Deleting is not archiving. A deleted todo is gone, not filed away; alt+z is the way
back, and there is one level of it, because undo here is for the delete you have just
regretted rather than a history to walk backwards through.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual.widgets import ListView

from tasky_tui import archive
from tasky_tui.models import Todo

if TYPE_CHECKING:
    from tasky_tui.app import TaskyApp


@dataclass(slots=True)
class Deleted:
    """A deleted todo, and enough about where it was to put it back."""

    todo: Todo
    index: int
    from_archive: bool


async def delete(app: TaskyApp) -> None:
    # The highlight has not moved while you were editing, so this is the todo in the
    # input bar: drop the half-finished edit and delete what it named.
    app.end_edit()
    item = app.highlighted()
    if item is None:
        app.notify("Nothing to delete.", severity="warning")
        return

    todo = item.todo
    todo_list = app.query_one("#todos", ListView)

    if app.viewing_archive:
        app.store.delete_from_archive(todo)
        # index is where it sat in the working list, which this todo has none of.
        # Undo appends it back to the archive, so it never needs one.
        app.deleted = Deleted(todo=todo, index=0, from_archive=True)
    else:
        app.deleted = Deleted(
            todo=todo,
            index=app.position_of(todo),
            from_archive=False,
        )
        app.todos = [entry for entry in app.todos if entry is not todo]
        app.store.save(app.todos)

    # The row's position, not the todo's: in the archive view the two run in opposite
    # directions, and it is the row we are about to take out. A row is highlighted --
    # highlighted() just gave us the todo in it -- so it exists.
    row = todo_list.index or 0

    # pop() rather than a full redraw, so the highlight stays where you left it and the
    # next delete is the next todo down, not the top of the list.
    await todo_list.pop(row)
    app.ensure_highlight(todo_list)
    app.refresh_status(len(todo_list.children))
    # The todo took its place in a project's count with it.
    await app.refresh_projects()
    app.refresh_bindings()
    app.notify(f"Deleted {todo.text!r} · alt+z to undo.")


async def undo(app: TaskyApp) -> None:
    if app.deleted is None:
        app.notify("Nothing to undo.", severity="warning")
        return

    app.end_edit()
    deleted, app.deleted = app.deleted, None

    if deleted.from_archive:
        app.store.restore_to_archive(deleted.todo)
        if app.viewing_archive:
            await archive.show(app)
    else:
        app.todos.insert(deleted.index, deleted.todo)
        # It comes back filed where it was, in a project that is still there: deleting
        # a todo does not touch the project it was in, so there is nothing to restore
        # but the todo itself.
        app.persist()
        if not app.viewing_archive:
            await app.show(app.shown())

    app.refresh_bindings()
    app.notify(f"Restored {deleted.todo.text!r}.")
