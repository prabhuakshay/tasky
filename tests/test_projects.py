"""Projects, from the file up: what is written down, and the two ways a todo is filed."""

import json

from conftest import add_todo, rows, show_project
from textual.widgets import Input, Static

from tasky_tui.app import TaskyApp
from tasky_tui.models import Project, Todo, project_named, project_of
from tasky_tui.storage import TodoStore
from tasky_tui.widgets import MOVE_PLACEHOLDER


def todo_bar(app: TaskyApp) -> Input:
    return app.query_one("#new-todo", Input)


# What is written down


async def test_projects_survive_a_restart(store):
    store.save_projects([Project(name="groceries")])

    (loaded,) = TodoStore(store.path).load_projects()
    assert loaded.name == "groceries"


async def test_a_todo_remembers_the_project_it_is_filed_under(store):
    groceries = Project(name="groceries")
    store.save_projects([groceries])
    store.save([Todo(text="buy milk", project_id=groceries.id)])

    (loaded,) = TodoStore(store.path).load()
    assert loaded.project_id == groceries.id


async def test_a_todo_in_no_project_is_a_todo_in_no_project(store):
    store.save([Todo(text="buy milk")])

    (loaded,) = store.load()
    assert loaded.project_id is None
    assert project_of(loaded, []) is None


async def test_a_file_from_before_projects_existed_still_loads(store):
    """Purely additive: its todos are in no project, and tasky does not invent one."""
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text(
        json.dumps({"version": 3, "todos": [{"text": "buy milk", "done": False}]}),
        encoding="utf-8",
    )

    (loaded,) = store.load()
    assert loaded.text == "buy milk"
    assert loaded.project_id is None
    assert store.load_projects() == []


async def test_an_id_naming_a_project_that_is_gone_shows_no_project(store):
    """An archived todo remembering a project you have since thrown away."""
    orphan = Todo(text="buy milk", project_id="a-project-that-was-deleted")

    assert project_of(orphan, [Project(name="groceries")]) is None


async def test_a_project_is_found_by_name_whatever_the_case(store):
    """So #Groceries and #groceries are one project, not two."""
    groceries = Project(name="groceries")

    assert project_named("GROCERIES", [groceries]) is groceries
    assert project_named("health", [groceries]) is None


async def test_a_corrupt_projects_file_is_moved_aside_rather_than_overwritten(store):
    store.projects_path.parent.mkdir(parents=True, exist_ok=True)
    store.projects_path.write_text("{not json", encoding="utf-8")

    assert store.load_projects() == []
    assert store.projects_quarantine_path.read_text(encoding="utf-8") == "{not json"


async def test_an_archived_todo_keeps_the_project_it_was_filed_under(store):
    groceries = Project(name="groceries")
    store.save_projects([groceries])
    store.archive_completed([Todo(text="buy milk", done=True, project_id=groceries.id)])

    (archived,) = store.load_archive()
    assert archived.project_id == groceries.id

    # And the project is still in projects.json to be found, which is why it is a file
    # of its own: archive.jsonl could never have held it.
    found = project_of(archived, store.load_projects())
    assert found is not None and found.name == "groceries"


async def test_archiving_in_a_project_leaves_the_other_projects_alone(store):
    """alt+a acts on the list in front of you, and in a project that is not all of it."""
    groceries = Project(name="groceries")
    milk = Todo(text="buy milk", done=True, project_id=groceries.id)
    rent = Todo(text="pay rent", done=True)

    remaining = store.archive_completed([milk, rent], project=groceries)

    assert [todo.text for todo in remaining] == ["pay rent"]  # still completed, still there
    assert [todo.text for todo in store.load_archive()] == ["buy milk"]


# Filing a todo as you type it


async def test_a_tag_files_the_todo_and_makes_the_project(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")

        (groceries,) = app.projects
        assert groceries.name == "groceries"
        assert app.todos[0].text == "buy milk"
        assert app.todos[0].project_id == groceries.id

    saved = TodoStore(store.path).load_projects()
    assert [project.name for project in saved] == ["groceries"]


async def test_the_row_wears_the_tag_you_typed(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")

        assert rows(app) == ["○  buy milk  #groceries"]


async def test_the_same_name_twice_is_the_same_project(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")
        await add_todo(pilot, "buy bread #GROCERIES")

        assert [project.name for project in app.projects] == ["groceries"]
        assert app.todos[0].project_id == app.todos[1].project_id


async def test_a_tag_with_no_todo_is_not_a_todo(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "#groceries")

        assert app.todos == []
        assert app.projects == []  # the bar it wants is the one in the pane


async def test_alt_e_hands_back_the_tag_so_an_edit_does_not_unfile_the_todo(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")
        await pilot.press("alt+e")
        await pilot.pause()

        assert todo_bar(app).value == "buy milk #groceries"

        todo_bar(app).value = "buy oat milk #groceries"
        await pilot.press("enter")
        await pilot.pause()

        assert app.todos[0].text == "buy oat milk"
        assert app.todos[0].project_id == app.projects[0].id


async def test_rubbing_the_tag_out_takes_the_todo_out_of_the_project(store):
    """The line is the whole truth about the todo, and that is what makes it safe."""
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")
        await pilot.press("alt+e")
        await pilot.pause()
        todo_bar(app).value = "buy milk"
        await pilot.press("enter")
        await pilot.pause()

        assert app.todos[0].project_id is None
        assert rows(app) == ["○  buy milk"]
        # The project stays: it outlives the todos in it, which is the point of one.
        assert [project.name for project in app.projects] == ["groceries"]


# Filing a todo that is already there


async def test_alt_m_opens_the_bar_with_the_tag_begun(store):
    store.save([Todo(text="buy milk")])
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await pilot.press("alt+m")
        await pilot.pause()

        assert todo_bar(app).value == "buy milk #"
        assert todo_bar(app).placeholder == MOVE_PLACEHOLDER
        assert app.editing is app.todos[0]

        todo_bar(app).value = "buy milk #groceries"
        await pilot.press("enter")
        await pilot.pause()

        assert app.todos[0].project_id == app.projects[0].id
        assert rows(app) == ["○  buy milk  #groceries"]


async def test_alt_m_starts_the_tag_afresh_so_the_bare_marker_unfiles_the_todo(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")
        await pilot.press("alt+m")
        await pilot.pause()

        assert todo_bar(app).value == "buy milk #"  # not the project it is already in

        await pilot.press("enter")  # the bare marker, as it stands
        await pilot.pause()

        assert app.todos[0].project_id is None


async def test_escape_leaves_a_move_as_it_was(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")
        filed_under = app.todos[0].project_id

        await pilot.press("alt+m")
        await pilot.pause()
        todo_bar(app).value = "buy milk #health"
        await pilot.press("escape")
        await pilot.pause()

        assert app.todos[0].project_id == filed_under
        assert app.editing is None


async def test_alt_m_does_not_apply_in_the_archive(store):
    """What is archived is what happened, filing and all."""
    store.archive_completed([Todo(text="buy milk", done=True)])
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await pilot.press("alt+v")
        await pilot.pause()

        assert app.check_action("move_to_project", ()) is False

        await pilot.press("alt+m")
        await pilot.pause()

        assert app.editing is None


# Standing in a project


async def test_a_todo_added_in_a_project_joins_it(store):
    """Or the project would be a filter over your todos, not a place you are working."""
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")
        await show_project(pilot, "groceries")
        await add_todo(pilot, "buy bread")

        assert app.todos[1].text == "buy bread"
        assert app.todos[1].project_id == app.project.id
        assert rows(app) == ["○  buy milk", "○  buy bread"]


async def test_the_tag_is_not_repeated_down_a_list_that_is_one_project(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")

        assert rows(app) == ["○  buy milk  #groceries"]

        await show_project(pilot, "groceries")

        # Still filed under it -- alt+e would hand the tag back -- just not worth
        # saying on every row of a list that is already the project.
        assert rows(app) == ["○  buy milk"]
        assert app.todos[0].project_id == app.project.id


async def test_a_todo_edited_out_of_the_project_you_are_in_leaves_the_list(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")
        await add_todo(pilot, "buy bread #groceries")
        await show_project(pilot, "groceries")

        await pilot.press("alt+e")
        await pilot.pause()
        todo_bar(app).value = "buy milk #health"
        await pilot.press("enter")
        await pilot.pause()

        assert rows(app) == ["○  buy bread"]
        assert len(app.todos) == 2  # it left the list, not the app


async def test_the_status_line_and_the_header_say_which_project_you_are_in(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")
        await add_todo(pilot, "walk dog")
        await show_project(pilot, "groceries")

        assert "1 active in groceries" in str(app.query_one("#status", Static).render())
        assert app.sub_title == "groceries"

        await show_project(pilot, "All")

        assert "2 active" in str(app.query_one("#status", Static).render())
        assert app.sub_title == ""


async def test_archiving_in_a_project_leaves_the_todos_you_cannot_see(store):
    """alt+a sweeps up the list in front of you, not the ones behind it."""
    groceries = Project(name="groceries")
    store.save_projects([groceries])
    store.save(
        [
            Todo(text="buy milk", project_id=groceries.id),
            Todo(text="walk dog", done=True),  # completed, and in no project
        ]
    )
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await show_project(pilot, "groceries")
        await pilot.press("alt+a")
        await pilot.pause()

        assert store.load_archive() == []
        assert [todo.text for todo in app.todos] == ["buy milk", "walk dog"]
