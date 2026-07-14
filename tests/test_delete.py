"""Deleting a todo: alt+d to drop it, alt+z to take that back."""

from conftest import add_todo, rows
from textual.widgets import Input, ListView

from tasky_tui.app import TaskyApp, TodoItem
from tasky_tui.models import Todo
from tasky_tui.storage import TodoStore


async def delete_selected(pilot) -> None:
    await pilot.press("alt+d")
    await pilot.pause()


async def undo_delete(pilot) -> None:
    await pilot.press("alt+z")
    await pilot.pause()


async def test_deleting_removes_the_todo_and_persists(store):
    store.save([Todo(text="buy milk"), Todo(text="walk dog")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await delete_selected(pilot)  # the first row is highlighted

        assert [todo.text for todo in app.todos] == ["walk dog"]
        assert rows(app) == ["○  walk dog"]

    assert [todo.text for todo in TodoStore(store.path).load()] == ["walk dog"]


async def test_a_deleted_todo_is_not_archived(store):
    """Delete means gone, not filed away. The archive is for what you finished."""
    store.save([Todo(text="buy milk", done=True)])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await delete_selected(pilot)

    assert store.load_archive() == []


async def test_undo_puts_the_todo_back_where_it_was(store):
    """Back in its old position, not appended to the end -- that is what undo means."""
    store.save([Todo(text="buy milk"), Todo(text="walk dog"), Todo(text="pay rent")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        app.query_one("#todos", ListView).index = 1  # highlight 'walk dog'
        await pilot.pause()
        await delete_selected(pilot)
        assert [todo.text for todo in app.todos] == ["buy milk", "pay rent"]

        await undo_delete(pilot)

        assert [todo.text for todo in app.todos] == ["buy milk", "walk dog", "pay rent"]
        assert rows(app) == ["○  buy milk", "○  walk dog", "○  pay rent"]

    assert [todo.text for todo in TodoStore(store.path).load()] == [
        "buy milk",
        "walk dog",
        "pay rent",
    ]


async def test_an_undone_todo_comes_back_exactly_as_it_was(store):
    store.save([Todo(text="buy milk", done=True, completed_at="2026-07-14T09:00:00+00:00")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await delete_selected(pilot)
        await undo_delete(pilot)

        (restored,) = app.todos
        assert restored.done is True
        assert restored.completed_at == "2026-07-14T09:00:00+00:00"
        assert rows(app) == ["✓  buy milk"]


async def test_only_the_last_delete_can_be_undone(store):
    """One slot: undo is for the delete you just regretted, not a history."""
    store.save([Todo(text="buy milk"), Todo(text="walk dog")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await delete_selected(pilot)
        await delete_selected(pilot)
        assert app.todos == []

        await undo_delete(pilot)
        assert [todo.text for todo in app.todos] == ["walk dog"]

        await undo_delete(pilot)  # nothing left to undo
        assert [todo.text for todo in app.todos] == ["walk dog"]


async def test_the_highlight_stays_where_it_was(store):
    """Delete twice in a row and you delete two neighbours, not two random todos."""
    store.save([Todo(text="buy milk"), Todo(text="walk dog"), Todo(text="pay rent")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        todo_list = app.query_one("#todos", ListView)
        todo_list.index = 1  # 'walk dog'
        await pilot.pause()

        await delete_selected(pilot)

        assert todo_list.index == 1  # now 'pay rent', the next one down
        assert isinstance(todo_list.highlighted_child, TodoItem)
        assert todo_list.highlighted_child.todo.text == "pay rent"


async def test_deleting_the_last_row_keeps_a_highlight(store):
    store.save([Todo(text="buy milk"), Todo(text="walk dog")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        todo_list = app.query_one("#todos", ListView)
        todo_list.index = 1
        await pilot.pause()

        await delete_selected(pilot)

        assert todo_list.index == 0
        assert rows(app) == ["○  buy milk"]


async def test_deleting_an_empty_list_does_nothing(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await delete_selected(pilot)

        assert app.todos == []
        assert app.deleted is None


async def test_undo_with_nothing_deleted_does_nothing(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await undo_delete(pilot)

        assert [todo.text for todo in app.todos] == ["buy milk"]


async def test_undo_is_only_offered_once_there_is_something_to_undo(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        assert app.check_action("undo_delete", ()) is False

        await delete_selected(pilot)
        assert app.check_action("undo_delete", ()) is True

        await undo_delete(pilot)
        assert app.check_action("undo_delete", ()) is False


async def test_the_status_line_keeps_up_with_a_delete(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk")
        await add_todo(pilot, "walk dog")

        await delete_selected(pilot)

        assert "1 active" in str(app.query_one("#status").render())


async def test_deleting_mid_edit_drops_the_edit_and_deletes_the_todo(store):
    """The highlight has not moved, so alt+d deletes the todo you were editing."""
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+e")
        await pilot.pause()
        await delete_selected(pilot)

        assert app.editing is None
        assert app.query_one("#new-todo", Input).value == ""
        assert app.todos == []


async def test_deleting_in_the_archive_removes_it_from_the_archive(store):
    """Otherwise the archive is a one-way door, and never gets smaller."""
    store.archive_completed([Todo(text="buy milk", done=True)])
    store.archive_completed([Todo(text="pay rent", done=True)])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+v")
        await pilot.pause()
        assert [item.todo.text for item in app.query(TodoItem)] == ["pay rent", "buy milk"]

        await delete_selected(pilot)  # newest first, so this is 'pay rent'

        assert [item.todo.text for item in app.query(TodoItem)] == ["buy milk"]

    assert [todo.text for todo in store.load_archive()] == ["buy milk"]


async def test_deleting_from_the_archive_does_not_touch_the_working_list(store):
    store.save([Todo(text="walk dog")])
    store.archive_completed([Todo(text="buy milk", done=True), Todo(text="walk dog")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+v")
        await pilot.pause()
        await delete_selected(pilot)

        assert [todo.text for todo in app.todos] == ["walk dog"]
    assert [todo.text for todo in TodoStore(store.path).load()] == ["walk dog"]


async def test_undo_puts_an_archived_todo_back_in_the_archive(store):
    """Not onto the working list: it was archived, and undo is not alt+u."""
    store.archive_completed([Todo(text="buy milk", done=True)])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+v")
        await pilot.pause()
        await delete_selected(pilot)
        assert store.load_archive() == []

        await undo_delete(pilot)

        assert [item.todo.text for item in app.query(TodoItem)] == ["buy milk"]
        assert app.todos == []

    assert [todo.text for todo in store.load_archive()] == ["buy milk"]
