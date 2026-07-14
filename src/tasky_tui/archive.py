"""Filing completed todos away, and reading them back.

The archive is not a place of its own so much as a mode the list is in: the same rows,
showing what you finished instead of what is left. That is three keys' worth of
behaviour -- alt+a to file the completed ones, alt+v to look at them, alt+u to take one
back -- and it lives here so that app.py can keep the shape of the app rather than the
shape of the archive.

Functions taking the app, rather than a mixin: each one needs the whole of it -- the
store, the list, the rows on screen -- and saying so in the signature is plainer than
inheriting it and hoping.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tasky_tui import status
from tasky_tui.widgets import TodoInput

if TYPE_CHECKING:
    from tasky_tui.app import TaskyApp


async def show(app: TaskyApp) -> None:
    """Put the archive in the list. Newest first."""
    # Read it only now that it is being asked for, so startup never pays for it
    # however large it grows.
    archived = app.store.load_archive()
    archived.reverse()
    await app.show(archived)


async def archive_completed(app: TaskyApp) -> None:
    if app.viewing_archive:
        return
    # Archiving takes the todo you may be editing out of the list underneath the input
    # bar, so the edit has nowhere to land. Same for the two below.
    app.end_edit()
    completed = sum(todo.done for todo in app.todos)
    if not completed:
        app.notify("No completed todos to archive.", severity="warning")
        return

    app.todos = app.store.archive_completed(app.todos)
    await app.show(app.todos)
    app.notify(f"Archived {completed} completed {status.plural(completed, 'todo')}.")


async def toggle_view(app: TaskyApp) -> None:
    app.end_edit()
    app.viewing_archive = not app.viewing_archive
    app.sub_title = "archive" if app.viewing_archive else ""

    if app.viewing_archive:
        await show(app)
    else:
        await app.show(app.todos)

    entry = app.query_one("#new-todo", TodoInput)
    entry.disabled = app.viewing_archive
    if not app.viewing_archive:
        entry.focus()
    app.refresh_bindings()


async def unarchive(app: TaskyApp) -> None:
    if not app.viewing_archive:
        return
    app.end_edit()
    item = app.highlighted()
    if item is None:
        app.notify("Nothing to restore.", severity="warning")
        return

    app.todos = app.store.unarchive(item.todo, app.todos)
    await show(app)
    app.notify(f"Restored {item.todo.text!r} to your list.")
