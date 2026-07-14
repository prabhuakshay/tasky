"""Clearing everything: the command palette's one irreversible offer.

The tests that matter most here are the ones where nothing happens. A confirmation is
only worth having if the ways of saying no outnumber the ways of saying yes, and if the
answer you get for doing nothing is the safe one.
"""

from conftest import add_todo, projects, rows
from textual.widgets import Button

from tasky_tui import status
from tasky_tui.app import TaskyApp
from tasky_tui.clearing import ConfirmClear
from tasky_tui.models import Note, Project, Todo
from tasky_tui.storage import TodoStore
from tasky_tui.widgets import TodoInput


async def open_clear(pilot) -> None:
    """What the command palette's "Clear everything" does, without driving the palette."""
    await pilot.app.action_clear_all()
    await pilot.pause()


async def type_word(pilot, word: str) -> None:
    confirm_box(pilot.app).value = word
    await pilot.pause()


async def confirm(pilot, word: str = "clear") -> None:
    """Say yes the way a user has to: type the word, then press enter."""
    await open_clear(pilot)
    await type_word(pilot, word)
    await pilot.press("enter")
    await pilot.pause()


# Through app.screen, not app: the app's own query starts at the default screen, and
# the screen we are asking about is the modal standing in front of it.
def confirm_box(app: TaskyApp) -> TodoInput:
    return app.screen.query_one("#confirm-word", TodoInput)


def clear_button(app: TaskyApp) -> Button:
    return app.screen.query_one("#clear", Button)


def a_full_tasky(store: TodoStore) -> None:
    """A tasky with something of everything in it, so clearing has all of it to take.

    Everything goes through archive_completed, which takes the whole working list, files
    the completed ones and saves back what is left -- so this ends up with two todos (one
    of them filed, one of them annotated) and two archived ones, and not with a working
    list that a later save has quietly overwritten.
    """
    groceries = Project(name="groceries")
    store.save_projects([groceries])
    store.archive_completed(
        [
            Todo(text="buy milk", project_id=groceries.id, notes=[Note(text="oat, not soya")]),
            Todo(text="walk dog"),
            Todo(text="pay rent", done=True, notes=[Note(text="due friday")]),
            Todo(text="book dentist", done=True),
        ]
    )


# The screen itself: what it says, and what it takes to get past it.


async def test_the_command_asks_before_it_does_anything(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await open_clear(pilot)

        assert isinstance(app.screen, ConfirmClear)
        # Asked, and nothing done about it yet.
        assert [todo.text for todo in app.todos] == ["buy milk"]
    assert [todo.text for todo in TodoStore(store.path).load()] == ["buy milk"]


async def test_the_screen_counts_out_what_it_is_about_to_take(store):
    """"Everything" is a word. A number is a fact, and the fact is what stops you."""
    a_full_tasky(store)

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await open_clear(pilot)

        toll = str(app.screen.query_one("#confirm-toll").render())
        assert toll == "This deletes 2 todos, 2 notes, 2 archived todos and 1 project."


async def test_the_button_is_dead_until_the_word_is_right(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await open_clear(pilot)
        assert clear_button(app).disabled is True

        await type_word(pilot, "clea")
        assert clear_button(app).disabled is True

        await type_word(pilot, "clear")
        assert clear_button(app).disabled is False

        # And dead again if you take it back.
        await type_word(pilot, "clearr")
        assert clear_button(app).disabled is True


async def test_the_word_is_a_word_not_a_keystroke(store):
    """Case and stray spaces are not the test. Having typed it is the test."""
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await open_clear(pilot)
        await type_word(pilot, "  Clear ")

        assert clear_button(app).disabled is False


# Saying no, which a confirmation had better be good at.


async def test_escape_says_no_and_nothing_is_touched(store):
    a_full_tasky(store)

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await open_clear(pilot)
        await pilot.press("escape")
        await pilot.pause()

        assert not isinstance(app.screen, ConfirmClear)
        assert [todo.text for todo in app.todos] == ["buy milk", "walk dog"]

    assert len(TodoStore(store.path).load()) == 2
    assert len(store.load_archive()) == 2
    assert len(store.load_projects()) == 1


async def test_cancel_says_no_even_with_the_word_typed(store):
    """The word arms the button. It does not press it."""
    a_full_tasky(store)

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await open_clear(pilot)
        await type_word(pilot, "clear")
        app.screen.query_one("#cancel", Button).press()
        await pilot.pause()

        assert not isinstance(app.screen, ConfirmClear)
        assert [todo.text for todo in app.todos] == ["buy milk", "walk dog"]

    assert len(TodoStore(store.path).load()) == 2


async def test_enter_on_a_half_typed_word_does_nothing_at_all(store):
    """Not confirm, and not cancel either: you are plainly mid-answer."""
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await open_clear(pilot)
        await type_word(pilot, "cle")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, ConfirmClear)  # still asking
        assert [todo.text for todo in app.todos] == ["buy milk"]


async def test_the_shortcuts_behind_the_screen_are_switched_off(store):
    """alt+d behind a modal would delete a todo you cannot see, to answer a question
    you were not asked."""
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await open_clear(pilot)

        assert app.check_action("delete", ()) is False
        assert app.check_action("edit", ()) is False
        assert app.check_action("archive_completed", ()) is False
        assert app.check_action("notes", ()) is False
        # Leaving without answering destroys nothing, so it stays possible.
        assert app.check_action("quit", ()) is True


async def test_an_alt_key_behind_the_screen_is_not_typed_into_the_box(store):
    """A switched-off binding does not consume its key -- TodoInput is what stops the
    letter landing in the box as if you had typed it."""
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await open_clear(pilot)
        await pilot.press("alt+d")
        await pilot.pause()

        assert confirm_box(app).value == ""
        assert [todo.text for todo in app.todos] == ["buy milk"]


# Saying yes.


async def test_confirming_clears_everything_from_the_app_and_the_disk(store):
    a_full_tasky(store)

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await confirm(pilot)

        assert app.todos == []
        assert app.projects == []
        assert rows(app) == []
        assert projects(app) == ["All"]

    fresh = TodoStore(store.path)
    assert fresh.load() == []
    assert fresh.load_archive() == []
    assert fresh.load_projects() == []


async def test_the_old_files_are_set_aside_rather_than_destroyed(store):
    a_full_tasky(store)

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await confirm(pilot)

    for path in (store.path, store.archive_path, store.projects_path):
        assert not path.exists()
        assert store.cleared_path(path).exists()

    # And what is in them is what was in the originals: a rope, not a gesture.
    salvaged = TodoStore(store.cleared_path(store.path))
    assert [todo.text for todo in salvaged.load()] == ["buy milk", "walk dog"]


async def test_clearing_twice_keeps_only_the_last_way_back(store):
    """One deep, the same bargain alt+z strikes."""
    store.save([Todo(text="the first tasky")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await confirm(pilot)
        await add_todo(pilot, "the second tasky")
        await confirm(pilot)

    salvaged = TodoStore(store.cleared_path(store.path))
    assert [todo.text for todo in salvaged.load()] == ["the second tasky"]


async def test_a_cleared_tasky_still_works(store):
    """Start afresh means start, not merely stop."""
    a_full_tasky(store)

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await confirm(pilot)
        await add_todo(pilot, "begin again #anew")

        assert rows(app) == ["○  begin again  #anew"]
        assert projects(app) == ["All", "anew"]

    fresh = TodoStore(store.path)
    assert [todo.text for todo in fresh.load()] == ["begin again"]
    assert [project.name for project in fresh.load_projects()] == ["anew"]


async def test_clearing_puts_you_back_where_tasky_starts(store):
    """You cannot be left standing in a project, or reading an archive, that is gone."""
    a_full_tasky(store)

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+v")  # into the archive
        await pilot.pause()
        assert app.viewing_archive is True

        await confirm(pilot)

        assert app.viewing_archive is False
        assert app.project is None

        # The archive disables the bar, because the archive is the one place tasky will
        # not take a new todo. Clear from in there and the bar has to come back, or you
        # start afresh in front of something that will not take a word.
        bar = app.query_one("#new-todo", TodoInput)
        assert bar.disabled is False
        assert app.focused is bar

        # And it means it: the proof of a bar you can type in is a todo typed into it.
        await add_todo(pilot, "begin again")
        assert rows(app) == ["○  begin again"]


async def test_clearing_empties_the_undo_slot(store):
    """alt+z afterwards would put one lone survivor back into a list you just emptied."""
    store.save([Todo(text="buy milk"), Todo(text="walk dog")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+d")  # delete 'buy milk', so there is something to undo
        await pilot.pause()
        assert app.deleted is not None

        await confirm(pilot)
        assert app.deleted is None

        await pilot.press("alt+z")
        await pilot.pause()

        assert app.todos == []
        assert rows(app) == []


async def test_clearing_an_empty_tasky_asks_nothing(store):
    """There is no question to ask, so it does not ask one."""
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await open_clear(pilot)

        assert not isinstance(app.screen, ConfirmClear)
        assert app.todos == []


async def test_a_tasky_with_no_projects_file_clears_without_complaint(store):
    """Nothing there to set aside is not a failure to set it aside."""
    store.save([Todo(text="buy milk")])
    assert not store.projects_path.exists()

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await confirm(pilot)

        assert app.todos == []


async def test_the_command_is_in_the_palette_and_not_on_a_key(store):
    """The one thing tasky cannot take back is not a thing your fingers can do."""
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        commands = [command.title for command in app.get_system_commands(app.screen)]
        assert "Clear everything" in commands

        assert not any(binding.action == "clear_all" for binding in TaskyApp.BINDINGS)


# The sentence itself, which needs no app to decide and so is tested without one.


def test_the_toll_names_each_thing_and_pluralises_it():
    assert status.to_clear(todos=1, notes=0, archived=0, projects=0) == "1 todo"
    assert status.to_clear(todos=2, notes=0, archived=0, projects=0) == "2 todos"
    assert status.to_clear(todos=0, notes=0, archived=1, projects=0) == "1 archived todo"
    assert status.to_clear(todos=0, notes=0, archived=3, projects=0) == "3 archived todos"


def test_the_toll_leaves_out_what_you_do_not_have():
    """A nought in a sentence meant to give you pause reads as reassurance."""
    assert status.to_clear(todos=3, notes=0, archived=0, projects=0) == "3 todos"
    assert status.to_clear(todos=3, notes=0, archived=0, projects=2) == "3 todos and 2 projects"


def test_the_toll_reads_as_a_sentence():
    assert status.to_clear(todos=1, notes=2, archived=3, projects=4) == (
        "1 todo, 2 notes, 3 archived todos and 4 projects"
    )
