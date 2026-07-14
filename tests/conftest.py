import pytest
from textual.widgets import Input, Label, ListView

from tasky_tui.app import TaskyApp, TodoItem
from tasky_tui.storage import TodoStore
from tasky_tui.widgets import NoteItem, ProjectItem


@pytest.fixture
def store(tmp_path):
    return TodoStore(tmp_path / "todos.json")


async def add_todo(pilot, text: str) -> None:
    # Type it into the bar, standing in the bar: enter means "add this" there, and
    # "complete the highlighted todo" one tab away, and the difference matters as soon
    # as a test has been anywhere else first.
    entry = pilot.app.query_one("#new-todo", Input)
    entry.focus()
    entry.value = text
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()


async def complete_selected(pilot) -> None:
    """Press enter on the highlighted todo, which is what completes it."""
    pilot.app.query_one("#todos", ListView).focus()
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()


def rows(app: TaskyApp) -> list[str]:
    """The text of each todo row, marker and all."""
    return [str(item.query_one(".text", Label).render()) for item in app.query(TodoItem)]


def dates(app: TaskyApp) -> list[tuple[str, str]]:
    """The (added, completed) date cells of each todo row."""
    cells = []
    for item in app.query(TodoItem):
        added, completed = list(item.query(".date"))
        cells.append((str(added.render()), str(completed.render())))
    return cells


def note_counts(app: TaskyApp) -> list[str]:
    """The notes cell of each todo row."""
    return [str(item.query_one(".notes", Label).render()) for item in app.query(TodoItem)]


async def enter_drawer(pilot) -> None:
    """Step across into the notes drawer, where the note keys are."""
    await pilot.press("alt+n")
    await pilot.pause()


async def leave_drawer(pilot) -> None:
    """Escape back to the todo list, where the todo keys are."""
    await pilot.press("escape")
    await pilot.pause()


async def write_note(pilot, text: str) -> None:
    """Type into the drawer's bar and submit it: a new note, or an edited one."""
    note_bar(pilot.app).value = text
    await pilot.press("enter")
    await pilot.pause()


def note_bar(app: TaskyApp) -> Input:
    """The bar you write notes in, as against the one you write todos in."""
    return app.query_one("#new-note", Input)


def notes(app: TaskyApp) -> list[str]:
    """The text of each note in the drawer."""
    return [str(item.query_one(".text", Label).render()) for item in app.query(NoteItem)]


def note_whens(app: TaskyApp) -> list[str]:
    """The line under each note: when it was written, and when it was last rewritten."""
    return [str(item.query_one(".when", Label).render()) for item in app.query(NoteItem)]


async def enter_projects(pilot) -> None:
    """Step across into the projects pane, where the project keys are."""
    await pilot.press("alt+p")
    await pilot.pause()


def project_bar(app: TaskyApp) -> Input:
    """The bar you name projects in, as against the ones for todos and notes."""
    return app.query_one("#new-project", Input)


def projects(app: TaskyApp) -> list[str]:
    """The name of each row of the projects pane -- "All" first, and it is not one."""
    return [str(item.query_one(".text", Label).render()) for item in app.query(ProjectItem)]


def project_counts(app: TaskyApp) -> list[str]:
    """The count beside each project: what is left to do in it."""
    return [str(item.query_one(".count", Label).render()) for item in app.query(ProjectItem)]


async def stand_on_project(pilot, name: str) -> None:
    """Move the pane's highlight onto a project, without going into it."""
    await enter_projects(pilot)
    rows = pilot.app.query_one("#project-list", ListView)
    rows.index = projects(pilot.app).index(name)
    rows.focus()
    await pilot.pause()


async def show_project(pilot, name: str) -> None:
    """Step into the pane and press enter on a project, which is what shows it."""
    await stand_on_project(pilot, name)
    await pilot.press("enter")
    await pilot.pause()
