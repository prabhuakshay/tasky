"""Shortcuts must fire while the new-todo Input has focus -- which it does at startup.

These tests deliberately do not use ``pilot.press()``. Textual builds its synthetic
key events with ``character=None`` for any multi-part key like "alt+a", but a real
terminal sends alt+<letter> with the bare letter attached. That difference matters:
``Input._on_key`` treats a key with a printable character as typing, inserts it, and
stops the event before the App can act on it. So ``pilot.press("alt+a")`` passes even
when the app is broken in a terminal. We send the terminal's version instead.
"""

import pytest
from textual import events
from textual.widgets import Input

from tasky_tui.app import TaskyApp
from tasky_tui.storage import Todo, TodoStore


@pytest.fixture
def store(tmp_path):
    return TodoStore(tmp_path / "todos.json")


async def press_as_terminal(pilot, key: str, character: str) -> None:
    """Send a key the way a terminal does, with the character still attached."""
    event = events.Key(key, character)
    event.set_sender(pilot.app)
    pilot.app._driver.send_message(event)
    await pilot.pause()


async def test_archive_shortcut_fires_while_typing(store):
    store.save([Todo(text="buy milk", done=True)])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        assert app.focused is app.query_one("#new-todo", Input)

        await press_as_terminal(pilot, "alt+a", "a")

        assert [todo.text for todo in store.load_archive()] == ["buy milk"]


async def test_archive_view_shortcut_fires_while_typing(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await press_as_terminal(pilot, "alt+v", "v")

        assert app.viewing_archive is True


async def test_quit_shortcut_fires_while_typing(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await press_as_terminal(pilot, "alt+q", "q")

        assert app._exit is True


async def test_shortcut_is_not_typed_into_the_input(store):
    """The failure mode was alt+a silently inserting an "a" instead of archiving."""
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await press_as_terminal(pilot, "alt+a", "a")
        await press_as_terminal(pilot, "alt+v", "v")

        assert app.query_one("#new-todo", Input).value == ""


async def test_plain_letters_still_type_normally(store):
    """The fix must not stop ordinary typing from reaching the Input."""
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        for character in "avq":
            await press_as_terminal(pilot, character, character)

        assert app.query_one("#new-todo", Input).value == "avq"
