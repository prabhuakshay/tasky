"""The bar you type todos into, and the two things typing into it can mean.

One bar, whether the text is headed for a new todo or an old one, rather than a second
one that is empty and in the way every moment you are not editing. Which of the two it
is doing is what app.editing says, and the bar says so too: it changes colour and it
changes what it asks you for.

The line in it is the whole truth about the todo -- the project on the end of it
included (see tags.py). That is what lets alt+e hand the line back to you unchanged,
and it is what makes rubbing the tag out mean what it looks like it means.

Functions taking the app, as in archive.py: app.py keeps the shape of the app, and
what the keys do lives beside the other keys.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import ListView

from tasky_tui import filing, tags
from tasky_tui.models import Todo
from tasky_tui.widgets import ADD_PLACEHOLDER, EDIT_PLACEHOLDER, TodoInput

if TYPE_CHECKING:
    from tasky_tui.app import TaskyApp


async def submit(app: TaskyApp, event: TodoInput.Submitted) -> None:
    """Enter, in the todo bar: add what was typed, or save the todo being edited."""
    text, name = tags.split(event.value)
    if not text:
        # Nothing typed is nothing to add. Mid-edit it is a mistake worth saying out
        # loud, since the alternative reading -- blank the todo -- is really a delete,
        # and there is a key for that. A bare "#groceries" is worth answering too: it
        # is a project with no todo, and the bar it wants is the one in the pane.
        if app.editing is not None:
            app.notify("A todo needs some text.", severity="warning")
        elif name:
            app.notify("A todo needs some text — alt+p to add a project on its own.")
        return

    if app.editing is not None:
        await save(app, text, name)
        return

    todo = Todo(text=text)
    # No tag means the project the list is showing. Adding a todo while standing in a
    # project and watching it land somewhere else would make the project a filter over
    # your todos rather than a place you are working in.
    todo.file_under(filing.named(app, name) if name else app.project)
    app.todos.append(todo)

    todo_list = app.query_one("#todos", ListView)
    await todo_list.append(app.row_for(todo))
    app.ensure_highlight(todo_list)
    event.input.clear()
    app.persist()
    await app.refresh_projects()


def edit(app: TaskyApp) -> None:
    """alt+e: open the highlighted todo in the bar, with its text already in it."""
    if app.viewing_archive:
        # What is archived is what happened. Restore it (alt+u) to change it.
        return
    item = app.highlighted()
    if item is None:
        app.notify("Nothing to edit.", severity="warning")
        return

    app.editing = item.todo
    entry = app.query_one("#new-todo", TodoInput)
    # Tag and all: the bar hands back the line you typed, so an edit that leaves the
    # tag alone leaves the filing alone. Anything else would make alt+e a way to
    # quietly unfile a todo you only meant to reword.
    entry.value = tags.join(item.todo.text, item.project.name if item.project else None)
    # Land at the end of the text, where you would be if you had just typed it.
    entry.cursor_position = len(entry.value)
    entry.placeholder = EDIT_PLACEHOLDER
    entry.add_class("editing")
    entry.focus()
    app.refresh_bindings()


async def save(app: TaskyApp, text: str, name: str | None) -> None:
    """Write the edited line back to the todo -- the text, and where it is filed."""
    assert app.editing is not None
    edited = app.editing
    edited.text = text
    # created_at stays: editing the wording of a todo does not make it a new one, and
    # it was still added when it was added.
    filing.refile(app, edited, name)
    app.end_edit()
    app.persist()
    # It may have just left one project's count and joined another's.
    await app.refresh_projects()
    # The list is showing a project, and this todo may have just left it -- in which
    # case its row has to go, or the project you are standing in is a suggestion.
    if app.project is not None and edited.project_id != app.project.id:
        await app.show(app.shown())


def end(app: TaskyApp) -> None:
    """Hand the bar back to adding todos. A no-op if it never left."""
    if app.editing is None:
        return
    app.editing = None
    entry = app.query_one("#new-todo", TodoInput)
    entry.clear()
    entry.placeholder = ADD_PLACEHOLDER
    entry.remove_class("editing")
    app.refresh_bindings()
