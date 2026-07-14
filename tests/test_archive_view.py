"""The archive as you meet it in the UI: alt+a to sweep, alt+v to look, alt+u to undo."""

from conftest import complete_selected, dates, rows
from textual.widgets import Input, Static

from tasky_tui.app import TaskyApp, TodoItem
from tasky_tui.storage import Todo, TodoStore


async def test_archiving_removes_completed_rows_from_the_list(store):
    store.save([Todo(text="buy milk", done=True), Todo(text="walk dog")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+a")
        await pilot.pause()

        assert [todo.text for todo in app.todos] == ["walk dog"]
        assert rows(app) == ["○  walk dog"]

    assert [todo.text for todo in store.load_archive()] == ["buy milk"]


async def test_archiving_with_nothing_completed_changes_nothing(store):
    store.save([Todo(text="walk dog")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+a")
        await pilot.pause()

        assert [todo.text for todo in app.todos] == ["walk dog"]
    assert not store.archive_path.exists()


async def test_archive_view_shows_archived_todos(store):
    store.save([Todo(text="buy milk", done=True), Todo(text="walk dog")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+a")
        await pilot.pause()
        assert rows(app) == ["○  walk dog"]

        await pilot.press("alt+v")
        await pilot.pause()

        assert app.viewing_archive is True
        assert rows(app) == ["✓  buy milk"]


async def test_archive_view_toggles_back_to_the_working_list(store):
    store.save([Todo(text="buy milk", done=True), Todo(text="walk dog")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+a")
        await pilot.press("alt+v")
        await pilot.pause()
        await pilot.press("alt+v")
        await pilot.pause()

        assert app.viewing_archive is False
        assert rows(app) == ["○  walk dog"]


async def test_archive_view_shows_newest_first(store):
    store.archive_completed([Todo(text="buy milk", done=True)])
    store.archive_completed([Todo(text="pay rent", done=True)])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+v")
        await pilot.pause()

        assert [item.todo.text for item in app.query(TodoItem)] == ["pay rent", "buy milk"]


async def test_the_archive_still_shows_when_a_todo_was_completed(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await complete_selected(pilot)
        await pilot.press("alt+a")  # archive it
        await pilot.press("alt+v")  # and go look at it
        await pilot.pause()

        ((_added, completed),) = dates(app)
        assert completed


async def test_unarchiving_restores_the_selected_todo(store):
    store.save([Todo(text="buy milk", done=True), Todo(text="walk dog")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+a")  # archive 'buy milk'
        await pilot.press("alt+v")  # look at the archive
        await pilot.pause()
        await pilot.press("alt+u")  # put it back
        await pilot.pause()

        assert not app.query(TodoItem)  # archive is now empty
        assert [todo.text for todo in app.todos] == ["walk dog", "buy milk"]

        await pilot.press("alt+v")  # back to the working list
        await pilot.pause()
        assert rows(app) == ["○  walk dog", "✓  buy milk"]

    assert store.load_archive() == []
    assert [todo.text for todo in store.load()] == ["walk dog", "buy milk"]


async def test_unarchived_todo_comes_back_still_completed(store):
    store.archive_completed([Todo(text="buy milk", done=True)])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+v")
        await pilot.pause()
        await pilot.press("alt+u")
        await pilot.pause()

        assert app.todos[0].done is True

        # ...and enter reopens it, which is the whole point of a true undo.
        await pilot.press("alt+v")
        await pilot.pause()
        await complete_selected(pilot)

        assert app.todos[0].done is False


async def test_unarchiving_an_empty_archive_does_nothing(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await pilot.press("alt+v")
        await pilot.pause()
        await pilot.press("alt+u")
        await pilot.pause()

        assert app.todos == []


async def test_restore_is_only_offered_inside_the_archive(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        assert app.check_action("unarchive", ()) is False
        assert app.check_action("archive_completed", ()) is True

        await pilot.press("alt+v")
        await pilot.pause()

        assert app.check_action("unarchive", ()) is True
        assert app.check_action("archive_completed", ()) is False


async def test_archive_view_is_read_only(store):
    store.archive_completed([Todo(text="buy milk", done=True)])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await pilot.press("alt+v")
        await pilot.pause()
        await complete_selected(pilot)

        assert app.query_one(TodoItem).todo.done is True
        assert [todo.done for todo in store.load_archive()] == [True]


async def test_typing_is_disabled_in_the_archive_view(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await pilot.press("alt+v")
        await pilot.pause()
        assert app.query_one("#new-todo", Input).disabled is True

        await pilot.press("alt+v")
        await pilot.pause()
        assert app.query_one("#new-todo", Input).disabled is False


async def test_startup_never_reads_the_archive(store, monkeypatch):
    """The archive can grow without bound, so opening tasky must not pay for it."""
    store.archive_completed([Todo(text="buy milk", done=True)])

    reads = []
    original = TodoStore.load_archive
    monkeypatch.setattr(
        TodoStore, "load_archive", lambda self: (reads.append(1), original(self))[1]
    )

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        assert reads == []

        await pilot.press("alt+v")
        await pilot.pause()
        assert reads == [1]


async def test_empty_archive_view_says_so(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await pilot.press("alt+v")
        await pilot.pause()

        assert not app.query(TodoItem)
        assert "Nothing archived yet" in str(app.query_one("#status", Static).render())
