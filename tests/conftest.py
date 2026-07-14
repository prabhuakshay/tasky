import pytest
from textual.widgets import Input, Label, ListView

from tasky_tui.app import TaskyApp, TodoItem
from tasky_tui.storage import TodoStore
from tasky_tui.widgets import NoteItem


@pytest.fixture
def store(tmp_path):
    return TodoStore(tmp_path / "todos.json")


async def add_todo(pilot, text: str) -> None:
    pilot.app.query_one("#new-todo", Input).value = text
    await pilot.press("enter")


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
