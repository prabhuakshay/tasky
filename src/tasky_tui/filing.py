"""Filing todos under projects: the tag on the bar, the alt+m key, and the pane's news.

A project is optional, and this is what that means in practice: nothing here happens
unless you ask for it. A todo with no tag on it goes in no project, and a tasky with
no projects in it is the tasky that was here before -- one pane fewer, and every key
meaning what it always did.

Filing a todo is one idea with two doors, because the moment you want it differs:

  the tag   You are typing the todo anyway, and you already know where it goes, so
            "buy milk #groceries" says so on the way past. The bar is the whole truth
            about the todo, tag and all (see tags.py) -- which is what lets alt+e hand
            the line back to you unchanged, and what makes rubbing the tag out mean
            what it looks like it means.

  alt+m     The todo is already there and the project is an afterthought, which is
            most of the time. It opens the same bar on the same todo with the tag
            started for you, so naming a project is a word and an enter rather than a
            trip to the end of a line you did not want to edit.

Both end up in file_under(), and neither is anywhere the other cannot reach.

Functions taking the app, as in archive.py: filing touches the store, the list, the
rows on screen and the pane, and a signature that says so beats a mixin that does not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import ListView

from tasky_tui import archive, tags
from tasky_tui.models import Project, Todo, project_named
from tasky_tui.widgets import MOVE_PLACEHOLDER, TodoInput

if TYPE_CHECKING:
    from tasky_tui.app import TaskyApp


def shown(app: TaskyApp) -> list[Todo]:
    """The todos the list is showing: all of them, or the ones in one project."""
    if app.project is None:
        return app.todos
    return [todo for todo in app.todos if todo.project_id == app.project.id]


def named(app: TaskyApp, name: str | None) -> Project | None:
    """The project of this name, making it if this is the first time it is named.

    Auto-creating is what makes the tag worth typing: "#groceries" is the whole of
    making a project, and there is no step between deciding to file something and
    having somewhere to file it. The pane is for the other jobs -- seeing what you
    have, renaming, throwing away -- not for asking permission.
    """
    if not name:
        return None
    existing = project_named(name, app.projects)
    if existing is not None:
        return existing

    project = Project(name=name)
    app.projects.append(project)
    app.store.save_projects(app.projects)
    return project


async def open_pane(app: TaskyApp) -> None:
    """Step across into the projects pane. alt+p, from wherever you are."""
    # A half-typed todo edit stays in the bar you left it in, and would be saved by an
    # enter you meant for a project. End it on the way out.
    app.end_edit()
    # Only means anything in a terminal too narrow to stand the pane beside the list,
    # where it is what puts the pane in front of the list instead (see app.tcss).
    app.screen.remove_class("-notes")
    app.screen.add_class("-projects")
    app.projects_pane.focus_projects()


def move(app: TaskyApp) -> None:
    """Name a project for the highlighted todo. alt+m."""
    if app.viewing_archive:
        # What is archived is what happened, filing and all. Restore it (alt+u) to
        # file it somewhere else.
        return
    item = app.highlighted()
    if item is None:
        app.notify("Nothing to file.", severity="warning")
        return

    # An edit, and the same edit alt+e opens -- the bar simply arrives with the tag
    # begun rather than the project already in it. So enter saves, escape leaves it as
    # it was, and enter on the bare "#" takes the todo out of the project it is in:
    # every one of those is a thing the bar already did.
    app.editing = item.todo
    entry = app.query_one("#new-todo", TodoInput)
    entry.value = tags.open_for(item.todo.text)
    entry.cursor_position = len(entry.value)
    entry.placeholder = MOVE_PLACEHOLDER
    entry.add_class("editing")
    entry.focus()
    app.refresh_bindings()


async def selected(app: TaskyApp, project: Project | None) -> None:
    """The pane says to show a project, or -- with None -- all of them again."""
    app.end_edit()
    app.project = project
    app.refresh_sub_title()

    if app.viewing_archive:
        await archive.show(app)
    else:
        await app.show(shown(app))

    # The pane is a control, and you came through it on the way to the list. Standing
    # in it afterwards would leave the todos you asked for over there, unhighlighted.
    app.screen.remove_class("-projects")
    app.query_one("#todos", ListView).focus()


async def changed(app: TaskyApp) -> None:
    """The pane made, renamed or threw away a project. Write it down, and redraw."""
    app.store.save_projects(app.projects)
    # Deleting a project unfiles the todos that were in it, and undoing that files them
    # back, so the todos may have changed as much as the projects have.
    app.store.save(app.todos)
    # Every row carries the name of its project, and a rename or a delete has just
    # changed what that name is -- or whether there is one.
    await app.show(shown(app))


def refile(app: TaskyApp, todo: Todo, name: str | None) -> None:
    """Put a todo in the project the bar just named, and redraw its row."""
    todo.file_under(named(app, name))
    item = app.item_for(todo)
    if item is not None:
        item.project = app.project_of(todo)
        item.refresh_todo()


