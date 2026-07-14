from conftest import add_todo, complete_selected, dates, rows
from textual.widgets import Input, ListView, Static

from tasky_tui.app import TaskyApp, TodoItem
from tasky_tui.storage import Todo, TodoStore


async def test_submitting_the_input_adds_a_todo(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk")

        assert [todo.text for todo in app.todos] == ["buy milk"]
        assert rows(app) == ["○  buy milk"]


async def test_input_is_cleared_after_adding(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk")

        assert app.query_one("#new-todo", Input).value == ""


async def test_blank_input_is_ignored(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "   ")

        assert app.todos == []
        assert not store.path.exists()


async def test_todos_survive_a_restart(store):
    async with TaskyApp(store=store).run_test() as pilot:
        await add_todo(pilot, "buy milk")
        await add_todo(pilot, "walk dog")

    restarted = TaskyApp(store=TodoStore(store.path))
    async with restarted.run_test():
        assert [todo.text for todo in restarted.todos] == ["buy milk", "walk dog"]


async def test_selecting_a_todo_toggles_it_done_and_persists(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk")
        await complete_selected(pilot)

        assert app.todos[0].done is True
        assert rows(app) == ["✓  buy milk"]

    (reloaded,) = TodoStore(store.path).load()
    assert reloaded.done is True


async def test_existing_todos_are_shown_on_start(store):
    store.save([Todo(text="buy milk", done=True)])

    app = TaskyApp(store=store)
    async with app.run_test():
        item = app.query_one(TodoItem)

        assert item.todo.text == "buy milk"
        assert item.has_class("done")


async def test_a_todo_containing_markup_is_shown_as_typed(store):
    # "[dim]" is valid Textual markup, so the label must not interpret it.
    store.save([Todo(text="buy [dim]milk[/dim]")])

    app = TaskyApp(store=store)
    async with app.run_test():
        assert rows(app) == ["○  buy [dim]milk[/dim]"]


async def test_status_line_surfaces_the_completed_backlog(store):
    store.save([Todo(text="buy milk", done=True), Todo(text="walk dog")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        status = app.query_one("#status", Static)
        assert "1 active" in str(status.render())
        assert "1 completed" in str(status.render())

        await pilot.press("alt+a")
        await pilot.pause()

        assert "completed" not in str(status.render())


async def test_the_list_names_its_date_columns(store):
    """Every row shows bare dates, so the header is what says what they mean."""
    app = TaskyApp(store=store)

    async with app.run_test():
        headings = [str(label.render()) for label in app.query("#columns Label")]

        assert headings == ["Todo", "Added", "Completed"]


async def test_a_new_todo_shows_when_it_was_created(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk")

        ((added, completed),) = dates(app)
        assert added  # a local date, whose exact text depends on the reader's timezone
        assert completed == ""


async def test_completing_a_todo_shows_and_records_when(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk")
        await complete_selected(pilot)

        assert app.todos[0].completed_at is not None
        ((_added, completed),) = dates(app)
        assert completed

    (reloaded,) = TodoStore(store.path).load()
    assert reloaded.completed_at == app.todos[0].completed_at


async def test_reopening_a_todo_drops_its_completion_date(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test() as pilot:
        await complete_selected(pilot)
        await complete_selected(pilot)  # and reopen it

        assert app.todos[0].completed_at is None
        ((_added, completed),) = dates(app)
        assert completed == ""


async def test_a_todo_completed_before_dates_were_recorded_shows_no_completion(store):
    """Todos written by an older tasky are done, with no record of when."""
    store.save([Todo(text="buy milk", done=True)])

    app = TaskyApp(store=store)
    async with app.run_test():
        ((added, completed),) = dates(app)

        assert added
        assert completed == ""


async def test_dates_are_shown_in_the_readers_own_timezone(store, monkeypatch):
    """Timestamps are stored as UTC, so they must be converted for display."""
    monkeypatch.setenv("TZ", "Asia/Kolkata")  # UTC+5:30, so the clock time differs
    import time

    time.tzset()

    store.save([Todo(text="buy milk", created_at="2026-07-14T09:00:00+00:00")])

    app = TaskyApp(store=store)
    async with app.run_test():
        ((added, _completed),) = dates(app)

        assert added == "14 Jul 14:30"


async def test_an_unparseable_date_does_not_break_the_list(store):
    """A hand-edited timestamp is a cosmetic problem, not a crash."""
    store.save([Todo(text="buy milk", created_at="last tuesday")])

    app = TaskyApp(store=store)
    async with app.run_test():
        ((added, _completed),) = dates(app)

        assert added == "last tuesday"
        assert rows(app) == ["○  buy milk"]


async def test_the_first_row_is_highlighted_so_enter_has_a_target(store):
    store.save([Todo(text="buy milk")])

    app = TaskyApp(store=store)
    async with app.run_test():
        assert app.query_one("#todos", ListView).index == 0


async def test_a_narrow_terminal_gives_the_room_to_the_todo_not_the_dates(store):
    store.save([Todo(text="file the quarterly expenses", done=True)])

    async with TaskyApp(store=store).run_test(size=(46, 16)) as pilot:
        assert not any(label.display for label in pilot.app.query(".date"))

    async with TaskyApp(store=store).run_test(size=(80, 16)) as pilot:
        assert all(label.display for label in pilot.app.query(".date"))


async def test_todo_rows_are_a_single_line(store):
    """The dates sit beside the todo, not under it."""
    store.save([Todo(text="buy milk", done=True), Todo(text="walk dog")])

    app = TaskyApp(store=store)
    async with app.run_test():
        assert [item.region.height for item in app.query(TodoItem)] == [1, 1]
