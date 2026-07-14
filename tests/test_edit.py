"""Editing a todo: alt+e to open it in the input bar, enter to save, escape to drop it."""

from conftest import add_todo, complete_selected, dates, rows
from textual.widgets import Input

from tasky_tui.app import TaskyApp
from tasky_tui.widgets import ADD_PLACEHOLDER, EDIT_PLACEHOLDER
from tasky_tui.models import Todo
from tasky_tui.storage import TodoStore


async def edit_selected(pilot, text: str | None = None) -> None:
    """Open the highlighted todo for editing, and optionally retype and save it."""
    await pilot.press("alt+e")
    await pilot.pause()
    if text is not None:
        pilot.app.query_one("#new-todo", Input).value = text
        await pilot.press("enter")
        await pilot.pause()


async def test_editing_a_todo_rewrites_it_and_persists(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await edit_selected(pilot, "buy oat milk")

        assert [todo.text for todo in app.todos] == ["buy oat milk"]
        assert rows(app) == ["○  buy oat milk"]

    (reloaded,) = TodoStore(store.path).load()
    assert reloaded.text == "buy oat milk"


async def test_editing_replaces_the_todo_rather_than_adding_another(store):
    """The bar that adds todos is the bar that edits them, so this is the risk."""
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await edit_selected(pilot, "buy oat milk")

        assert len(app.todos) == 1


async def test_edit_opens_with_the_todo_already_in_the_bar(store):
    """You are correcting a todo, not retyping it from nothing."""
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+e")
        await pilot.pause()

        entry = app.query_one("#new-todo", Input)
        assert entry.value == "buy milk"
        assert entry.cursor_position == len("buy milk")  # at the end, ready to type
        assert app.focused is entry


async def test_the_bar_says_it_is_editing_not_adding(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        entry = app.query_one("#new-todo", Input)
        assert entry.placeholder == ADD_PLACEHOLDER
        assert not entry.has_class("editing")

        await pilot.press("alt+e")
        await pilot.pause()

        assert entry.placeholder == EDIT_PLACEHOLDER
        assert entry.has_class("editing")


async def test_escape_leaves_the_todo_as_it_was(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+e")
        await pilot.pause()
        app.query_one("#new-todo", Input).value = "buy oat milk"
        await pilot.press("escape")
        await pilot.pause()

        assert app.editing is None
        assert [todo.text for todo in app.todos] == ["buy milk"]
        assert rows(app) == ["○  buy milk"]


async def test_the_bar_goes_back_to_adding_after_an_edit(store):
    """A cancelled edit must not leave its text behind to be added as a new todo."""
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+e")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()

        entry = app.query_one("#new-todo", Input)
        assert entry.value == ""
        assert entry.placeholder == ADD_PLACEHOLDER
        assert not entry.has_class("editing")

        await add_todo(pilot, "walk dog")
        assert [todo.text for todo in app.todos] == ["buy milk", "walk dog"]


async def test_an_empty_edit_is_refused_rather_than_blanking_the_todo(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await edit_selected(pilot, "   ")

        assert [todo.text for todo in app.todos] == ["buy milk"]
        assert app.editing is not None  # still editing, so you can fix it or escape


async def test_editing_keeps_when_the_todo_was_added(store):
    """Rewording a todo does not make it a new one."""
    store.save([Todo(text="buy milk", created_at="2026-07-14T09:00:00+00:00")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        added_before, _ = dates(app)[0]

        await edit_selected(pilot, "buy oat milk")

        assert app.todos[0].created_at == "2026-07-14T09:00:00+00:00"
        assert dates(app)[0][0] == added_before


async def test_editing_a_completed_todo_leaves_it_completed(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk")
        await complete_selected(pilot)
        completed_at = app.todos[0].completed_at

        await edit_selected(pilot, "buy oat milk")

        assert app.todos[0].done is True
        assert app.todos[0].completed_at == completed_at
        assert rows(app) == ["✓  buy oat milk"]


async def test_editing_an_empty_list_does_nothing(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await pilot.press("alt+e")
        await pilot.pause()

        assert app.editing is None
        assert app.todos == []


async def test_the_archive_cannot_be_edited(store):
    """What is archived is what happened. alt+u it back to the list to change it."""
    store.archive_completed([Todo(text="buy milk", done=True)])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+v")
        await pilot.pause()
        await pilot.press("alt+e")
        await pilot.pause()

        assert app.editing is None
        assert app.check_action("edit", ()) is False
        assert [todo.text for todo in store.load_archive()] == ["buy milk"]


async def test_leaving_for_the_archive_view_abandons_the_edit(store):
    """The edited todo is about to leave the list, so the edit has nowhere to land."""
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+e")
        await pilot.pause()
        await pilot.press("alt+v")
        await pilot.pause()

        assert app.editing is None
        assert app.query_one("#new-todo", Input).value == ""


async def test_archiving_mid_edit_abandons_the_edit(store):
    store.save([Todo(text="buy milk", done=True)])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+e")
        await pilot.pause()
        await pilot.press("alt+a")
        await pilot.pause()

        assert app.editing is None
        assert app.todos == []
        assert [todo.text for todo in store.load_archive()] == ["buy milk"]


async def test_cancel_is_only_offered_while_editing(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        assert app.check_action("cancel_edit", ()) is False

        await pilot.press("alt+e")
        await pilot.pause()

        assert app.check_action("cancel_edit", ()) is True
