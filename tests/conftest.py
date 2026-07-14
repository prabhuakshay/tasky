import pytest
from textual.widgets import Input, Label, ListView

from tasky_tui.app import TaskyApp, TodoItem
from tasky_tui.storage import TodoStore


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
