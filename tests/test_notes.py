"""Writing notes against a todo, editing them, and the dates they carry.

The drawer they live in -- following the highlight, and whose keys are whose -- is in
test_notes_drawer. Deleting one is in test_notes_delete.
"""

from conftest import (
    enter_drawer,
    note_bar,
    note_whens,
    notes,
    write_note,
)
from textual.widgets import Input, ListView

from tasky_tui.app import TaskyApp
from tasky_tui.storage import Note, Todo, TodoStore
from tasky_tui.widgets import ADD_NOTE_PLACEHOLDER, EDIT_NOTE_PLACEHOLDER


# Writing


async def test_a_todo_can_be_given_a_note(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await write_note(pilot, "oat, not soya")

        assert notes(app) == ["oat, not soya"]
        assert [note.text for note in app.todos[0].notes] == ["oat, not soya"]

    (reloaded,) = TodoStore(store.path).load()
    assert [note.text for note in reloaded.notes] == ["oat, not soya"]


async def test_a_todo_can_have_more_than_one_note(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await write_note(pilot, "oat, not soya")
        await write_note(pilot, "the corner shop stocks it")

        assert notes(app) == ["oat, not soya", "the corner shop stocks it"]

    (reloaded,) = TodoStore(store.path).load()
    assert [note.text for note in reloaded.notes] == [
        "oat, not soya",
        "the corner shop stocks it",
    ]


async def test_writing_a_note_does_not_add_a_todo(store):
    """Two bars on one screen, and the app is listening for a submit from one of them."""
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await write_note(pilot, "oat, not soya")

        assert [todo.text for todo in app.todos] == ["buy milk"]


async def test_an_empty_note_is_refused(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await write_note(pilot, "   ")

        assert app.todos[0].notes == []


async def test_notes_belong_to_the_todo_they_were_written_against(store):
    store.save([Todo(text="buy milk"), Todo(text="walk dog")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        todo_list = app.query_one("#todos", ListView)
        todo_list.focus()
        todo_list.index = 1  # walk dog
        await pilot.pause()

        await enter_drawer(pilot)
        await write_note(pilot, "the long way round")

        assert app.todos[0].notes == []
        assert [note.text for note in app.todos[1].notes] == ["the long way round"]


# When it was written, and when it was last rewritten


async def test_a_note_records_when_it_was_written(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await write_note(pilot, "oat, not soya")

        (note,) = app.todos[0].notes
        assert note.created_at
        # Never edited, so there is no edit date -- and the line under the note says
        # when it was written and stops there, rather than repeating itself.
        assert note.updated_at is None
        assert "edited" not in note_whens(app)[0]


async def test_editing_a_note_records_when_and_keeps_when_it_was_written(store):
    store.save([Todo(text="buy milk", notes=[Note(text="oat, not soya")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        written_at = app.todos[0].notes[0].created_at

        await enter_drawer(pilot)
        await pilot.press("alt+e")
        await pilot.pause()
        await write_note(pilot, "oat, not soya — the barista one")

        (note,) = app.todos[0].notes
        assert note.text == "oat, not soya — the barista one"
        assert note.created_at == written_at  # rewording it does not rewrite its past
        assert note.updated_at is not None
        assert "edited" in note_whens(app)[0]  # and the note says so too

        updated_at = note.updated_at

    (reloaded,) = TodoStore(store.path).load()
    assert reloaded.notes[0].updated_at == updated_at


# Editing


async def test_edit_opens_the_note_already_in_the_bar(store):
    store.save([Todo(text="buy milk", notes=[Note(text="oat, not soya")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await pilot.press("alt+e")
        await pilot.pause()

        entry = note_bar(app)
        assert entry.value == "oat, not soya"
        assert entry.cursor_position == len("oat, not soya")  # at the end, ready to type
        assert entry.placeholder == EDIT_NOTE_PLACEHOLDER
        assert app.focused is entry


async def test_editing_a_note_replaces_it_rather_than_adding_another(store):
    """The bar that writes notes is the bar that edits them, so this is the risk."""
    store.save([Todo(text="buy milk", notes=[Note(text="oat, not soya")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await pilot.press("alt+e")
        await pilot.pause()
        await write_note(pilot, "oat, not soya — the barista one")

        assert len(app.todos[0].notes) == 1


async def test_editing_a_note_leaves_the_todo_alone(store):
    """alt+e is the app's key. Standing in the drawer, it is the drawer's."""
    store.save([Todo(text="buy milk", notes=[Note(text="oat")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await pilot.press("alt+e")
        await pilot.pause()

        assert app.editing is None  # the todo is not the thing being edited
        assert app.query_one("#new-todo", Input).value == ""


async def test_enter_on_a_note_opens_it_for_editing(store):
    """Enter on a todo completes it. A note has nothing to complete, so it edits."""
    store.save([Todo(text="buy milk", notes=[Note(text="oat, not soya")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        app.query_one("#note-list", ListView).focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert note_bar(app).value == "oat, not soya"


async def test_escape_leaves_the_note_as_it_was_and_stays_in_the_drawer(store):
    """The first escape backs out of the edit, not the drawer: your text is in it."""
    store.save([Todo(text="buy milk", notes=[Note(text="oat, not soya")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await pilot.press("alt+e")
        await pilot.pause()
        note_bar(app).value = "soya after all"
        await pilot.press("escape")
        await pilot.pause()

        assert app.in_drawer()  # still here
        assert notes(app) == ["oat, not soya"]

        entry = note_bar(app)
        assert entry.value == ""
        assert entry.placeholder == ADD_NOTE_PLACEHOLDER

        await pilot.press("escape")  # and now it leaves
        await pilot.pause()

        assert not app.in_drawer()
        assert app.focused is app.query_one("#todos", ListView)


async def test_an_empty_edit_is_refused_rather_than_blanking_the_note(store):
    store.save([Todo(text="buy milk", notes=[Note(text="oat, not soya")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        await pilot.press("alt+e")
        await pilot.pause()
        await write_note(pilot, "   ")

        assert notes(app) == ["oat, not soya"]
        assert app.drawer.editing is not None  # still editing, so you can fix it
