"""Deleting a note, and undoing that: alt+d and alt+z, standing in the drawer.

Both keys are the app's, where they delete the todo you are on. In the drawer they
have to delete the note you are on and leave the todo alone -- so half of what these
tests are checking is which of the two panes a keypress reached.
"""

from conftest import enter_drawer, leave_drawer, notes, write_note

from tasky_tui.app import TaskyApp
from tasky_tui.storage import Note, Todo, TodoStore


async def test_a_note_can_be_deleted(store):
    store.save([Todo(text="buy milk", notes=[Note(text="oat"), Note(text="soya")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await pilot.press("alt+d")
        await pilot.pause()

        assert notes(app) == ["soya"]
        assert [note.text for note in app.todos[0].notes] == ["soya"]

    (reloaded,) = TodoStore(store.path).load()
    assert [note.text for note in reloaded.notes] == ["soya"]


async def test_deleting_a_note_leaves_the_todo_alone(store):
    """alt+d is the app's key. Standing in the drawer, it is the drawer's."""
    store.save([Todo(text="buy milk", notes=[Note(text="oat, not soya")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await pilot.press("alt+d")
        await pilot.pause()

        assert [todo.text for todo in app.todos] == ["buy milk"]
        assert app.todos[0].notes == []
        # The app deleted nothing, so it has nothing to put back either.
        assert app.deleted is None


async def test_undo_puts_the_note_back_where_it_was(store):
    store.save([Todo(text="buy milk", notes=[Note(text="oat"), Note(text="soya")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await pilot.press("alt+d")
        await pilot.pause()
        await pilot.press("alt+z")
        await pilot.pause()

        assert notes(app) == ["oat", "soya"]  # first again, not tacked on the end

    (reloaded,) = TodoStore(store.path).load()
    assert [note.text for note in reloaded.notes] == ["oat", "soya"]


async def test_undo_is_only_offered_with_a_delete_behind_you(store):
    store.save([Todo(text="buy milk", notes=[Note(text="oat")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        assert app.drawer.check_action("undo_delete", ()) is False

        await pilot.press("alt+d")
        await pilot.pause()

        assert app.drawer.check_action("undo_delete", ()) is True


async def test_deleting_the_note_you_are_editing_ends_the_edit(store):
    """The edit had nowhere to land: the note it was editing is gone."""
    store.save([Todo(text="buy milk", notes=[Note(text="oat")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await pilot.press("alt+e")
        await pilot.pause()
        await pilot.press("alt+d")
        await pilot.pause()

        assert app.drawer.editing is None
        assert app.todos[0].notes == []


async def test_the_undo_does_not_follow_you_to_another_todo(store):
    """It was a delete on the todo you were looking at, and you are not there now."""
    store.save(
        [
            Todo(text="buy milk", notes=[Note(text="oat")]),
            Todo(text="walk dog", notes=[Note(text="the long way round")]),
        ]
    )

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await pilot.press("alt+d")
        await pilot.pause()
        assert app.todos[0].notes == []

        await leave_drawer(pilot)
        todo_list = app.query_one("#todos")
        todo_list.index = 1  # walk dog, whose notes are its own
        await pilot.pause()
        await enter_drawer(pilot)

        assert app.drawer.check_action("undo_delete", ()) is False
        await pilot.press("alt+z")
        await pilot.pause()

        assert [note.text for note in app.todos[1].notes] == ["the long way round"]
        assert app.todos[0].notes == []  # and the deleted one stays deleted


async def test_the_todo_keys_come_back_when_you_leave_the_drawer(store):
    store.save([Todo(text="buy milk", notes=[Note(text="oat")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await leave_drawer(pilot)

        await pilot.press("alt+d")
        await pilot.pause()

        assert app.todos == []  # alt+d deletes the todo again
        assert app.deleted is not None


async def test_a_deleted_todo_takes_its_notes_with_it(store):
    store.save([Todo(text="buy milk", notes=[Note(text="oat")]), Todo(text="walk dog")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+d")
        await pilot.pause()

        assert [todo.text for todo in app.todos] == ["walk dog"]

        await pilot.press("alt+z")  # and undo brings them back with it
        await pilot.pause()

        assert [note.text for note in app.todos[0].notes] == ["oat"]

    (restored, _) = TodoStore(store.path).load()
    assert [note.text for note in restored.notes] == ["oat"]


async def test_writing_a_note_then_deleting_the_todo_still_saves(store):
    """The note was written into the todo in memory; the delete rewrites the file."""
    store.save([Todo(text="buy milk"), Todo(text="walk dog")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await write_note(pilot, "oat, not soya")
        await leave_drawer(pilot)

        await pilot.press("alt+d")
        await pilot.pause()

    (remaining,) = TodoStore(store.path).load()
    assert remaining.text == "walk dog"
    assert remaining.notes == []
