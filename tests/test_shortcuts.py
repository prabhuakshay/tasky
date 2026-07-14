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


async def test_edit_shortcut_fires_while_typing(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await press_as_terminal(pilot, "alt+e", "e")

        assert app.editing is not None
        assert app.query_one("#new-todo", Input).value == "buy milk"


async def test_delete_and_undo_shortcuts_fire_while_typing(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await press_as_terminal(pilot, "alt+d", "d")
        assert app.todos == []

        await press_as_terminal(pilot, "alt+z", "z")
        assert [todo.text for todo in app.todos] == ["buy milk"]


async def test_shortcut_is_not_typed_into_the_input(store):
    """The failure mode was alt+a silently inserting an "a" instead of archiving."""
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await press_as_terminal(pilot, "alt+a", "a")
        await press_as_terminal(pilot, "alt+v", "v")
        await press_as_terminal(pilot, "alt+d", "d")
        await press_as_terminal(pilot, "alt+z", "z")

        assert app.query_one("#new-todo", Input).value == ""


async def test_a_shortcut_is_not_typed_into_the_input_mid_edit_either(store):
    """The edit bar is the same Input, holding text you would hate to corrupt."""
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await press_as_terminal(pilot, "alt+e", "e")
        await press_as_terminal(pilot, "alt+z", "z")

        assert app.query_one("#new-todo", Input).value == "buy milk"


async def test_a_shortcut_that_does_not_apply_is_not_typed_either(store):
    """A binding switched off by check_action does not consume its key: Textual's
    run_action returns False and the event carries on to the focused widget. So
    every shortcut that can be switched off can also leave a letter in the bar.

    alt+u restores from the archive, and we are not in the archive. alt+z undoes a
    delete, and nothing has been deleted. alt+e edits, and there is nothing to edit.
    None of them do anything here, and none of them are text.
    """
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        for key, character in [("alt+u", "u"), ("alt+z", "z"), ("alt+e", "e")]:
            await press_as_terminal(pilot, key, character)

        assert app.query_one("#new-todo", Input).value == ""


async def test_the_archives_own_shortcuts_are_not_typed_there_either(store):
    """The mirror image: in the archive it is alt+a and alt+e that do not apply."""
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await press_as_terminal(pilot, "alt+v", "v")  # into the archive
        # The bar is disabled in the archive, so type into it on the way back out.
        await press_as_terminal(pilot, "alt+a", "a")
        await press_as_terminal(pilot, "alt+e", "e")
        await press_as_terminal(pilot, "alt+v", "v")

        assert app.query_one("#new-todo", Input).value == ""


async def test_plain_letters_still_type_normally(store):
    """The fix must not stop ordinary typing from reaching the Input."""
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        for character in "avqedz":
            await press_as_terminal(pilot, character, character)

        assert app.query_one("#new-todo", Input).value == "avqedz"
