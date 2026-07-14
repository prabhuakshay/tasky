"""The drawer itself: what it shows, and whose keys are whose.

The drawer is a second pane on the same screen as the todo list, so two things can go
wrong that could not when the notes were somewhere else. It can show the notes of the
wrong todo -- it follows the highlight, and the highlight moves. And a key can act on
the wrong pane: alt+e, alt+d and alt+z are the app's, bound with priority so they fire
while a bar has the focus, and in the drawer they have to mean the note in front of
you rather than the todo it belongs to.
"""

from conftest import (
    add_todo,
    complete_selected,
    enter_drawer,
    leave_drawer,
    note_bar,
    note_counts,
    notes,
    write_note,
)
from textual.widgets import ListView, Static

from tasky_tui.app import TaskyApp
from tasky_tui.storage import Note, Todo, TodoStore


def title(app: TaskyApp) -> str:
    """The todo the drawer says its notes belong to."""
    return str(app.query_one("#drawer-title", Static).render())


# What it shows


async def test_the_drawer_shows_the_notes_of_the_highlighted_todo(store):
    store.save([Todo(text="buy milk", notes=[Note(text="oat, not soya")])])

    app = TaskyApp(store=store)
    async with app.run_test():
        assert notes(app) == ["oat, not soya"]
        assert title(app) == "buy milk"


async def test_the_drawer_follows_the_highlight(store):
    """The point of a drawer and not a screen: run down the list, reading as you go."""
    store.save(
        [
            Todo(text="buy milk", notes=[Note(text="oat, not soya")]),
            Todo(text="walk dog", notes=[Note(text="the long way round")]),
        ]
    )

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        assert notes(app) == ["oat, not soya"]

        todo_list = app.query_one("#todos", ListView)
        todo_list.focus()
        todo_list.index = 1
        await pilot.pause()

        assert notes(app) == ["the long way round"]
        assert title(app) == "walk dog"


async def test_an_empty_list_leaves_the_drawer_with_nothing_to_show(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        assert notes(app) == []
        assert note_bar(app).disabled  # nothing to write a note against

        await add_todo(pilot, "buy milk")
        await pilot.pause()

        assert not note_bar(app).disabled  # and now there is


async def test_deleting_the_last_todo_empties_the_drawer(store):
    """The drawer was showing the notes of a todo that is not there any more."""
    store.save([Todo(text="buy milk", notes=[Note(text="oat, not soya")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+d")
        await pilot.pause()

        assert notes(app) == []
        assert note_bar(app).disabled


async def test_the_todo_row_says_how_many_notes_it_has(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        assert note_counts(app) == [""]  # nothing written against it, so it says nothing

        await enter_drawer(pilot)
        await write_note(pilot, "oat, not soya")
        await write_note(pilot, "the corner shop stocks it")

        assert note_counts(app) == ["✎ 2"]


# Whose keys are whose


async def test_tab_moves_between_the_bar_and_the_notes(store):
    """The app switches its own keys off in the drawer -- its own, and only its own.

    tab is bound to the app's focus_next, and switching that off along with the todo
    keys would leave the drawer a place you cannot tab out of the bar in.
    """
    store.save([Todo(text="buy milk", notes=[Note(text="oat")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await enter_drawer(pilot)
        assert app.focused is note_bar(app)

        await pilot.press("tab")
        await pilot.pause()
        assert app.focused is app.query_one("#note-list", ListView)

        await pilot.press("shift+tab")
        await pilot.pause()
        assert app.focused is note_bar(app)

        # Same story: the command palette is Textual's, not the todo list's.
        assert app.check_action("command_palette", ()) is True


async def test_the_todo_keys_are_off_in_the_drawer_and_on_again_outside_it(store):
    """The footer follows this, so it always offers the keys for the pane you are in."""
    store.save([Todo(text="buy milk", notes=[Note(text="oat")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        assert app.check_action("delete", ()) is True

        await enter_drawer(pilot)
        assert app.check_action("delete", ()) is False  # the drawer's alt+d, now
        assert app.check_action("archive_completed", ()) is False
        assert app.check_action("quit", ()) is True  # alt+q is alt+q wherever you are

        await leave_drawer(pilot)
        assert app.check_action("delete", ()) is True


async def test_alt_n_takes_you_to_the_drawer_from_either_bar(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        assert not app.in_drawer()

        await enter_drawer(pilot)

        assert app.in_drawer()
        assert app.focused is note_bar(app)


async def test_a_half_typed_todo_edit_ends_when_you_step_into_the_drawer(store):
    """It would otherwise be sitting in the other bar, waiting for an enter you meant
    for a note."""
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+e")
        await pilot.pause()
        assert app.editing is not None

        await enter_drawer(pilot)

        assert app.editing is None
        assert app.todos[0].text == "buy milk"


# The archive


async def test_notes_go_with_the_todo_when_it_is_archived(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk")
        await enter_drawer(pilot)
        await write_note(pilot, "oat, not soya")
        await leave_drawer(pilot)
        await complete_selected(pilot)
        await pilot.press("alt+a")
        await pilot.pause()

        (archived,) = store.load_archive()
        assert [note.text for note in archived.notes] == ["oat, not soya"]


async def test_the_archive_shows_its_notes_but_refuses_to_change_them(store):
    """What is archived is what happened, and the notes are part of what happened."""
    store.archive_completed([Todo(text="buy milk", done=True, notes=[Note(text="oat")])])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+v")
        await pilot.pause()

        assert notes(app) == ["oat"]  # read them
        assert note_bar(app).disabled  # but write none

        await enter_drawer(pilot)
        assert app.drawer.check_action("delete", ()) is False

        await pilot.press("alt+d")
        await pilot.pause()

        assert notes(app) == ["oat"]

    (archived,) = TodoStore(store.path).load_archive()
    assert [note.text for note in archived.notes] == ["oat"]
