"""The projects pane: where you stand to choose a project, and to change one.

The keys are the ones you already know -- alt+e, alt+d, alt+z -- and in here they mean
the project in front of you rather than the todo or the note. Which pane you are
standing in is what decides.
"""

from conftest import (
    add_todo,
    enter_projects,
    project_bar,
    project_counts,
    projects,
    rows,
    show_project,
    stand_on_project,
)
from textual.widgets import ListView, Static

from tasky_tui.app import TaskyApp
from tasky_tui.models import Project, Todo
from tasky_tui.storage import TodoStore


async def name_project(pilot, text: str) -> None:
    """Type into the pane's bar and submit it: a new project, or a renamed one."""
    entry = project_bar(pilot.app)
    entry.focus()
    entry.value = text
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()


# Coming into the pane


async def test_alt_p_lands_on_the_projects_because_choosing_one_is_why_you_came(store):
    store.save_projects([Project(name="groceries")])
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await enter_projects(pilot)

        assert app.in_projects()
        assert app.focused is app.query_one("#project-list", ListView)


async def test_alt_p_lands_in_the_bar_when_there_are_no_projects_to_choose_between(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await enter_projects(pilot)

        assert app.focused is project_bar(app)


async def test_all_comes_first_and_is_not_a_project(store):
    store.save_projects([Project(name="groceries"), Project(name="health")])
    app = TaskyApp(store=store)

    async with app.run_test():
        assert projects(app) == ["All", "groceries", "health"]
        assert str(app.query_one("#project-status", Static).render()) == "2 projects"


async def test_escape_gives_the_list_back(store):
    store.save_projects([Project(name="groceries")])
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await enter_projects(pilot)
        await pilot.press("escape")
        await pilot.pause()

        assert not app.in_projects()
        assert app.focused is app.query_one("#todos", ListView)


# Making a project


async def test_typing_a_name_makes_a_project_and_saves_it(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await enter_projects(pilot)
        await name_project(pilot, "groceries")

        assert [project.name for project in app.projects] == ["groceries"]
        assert projects(app) == ["All", "groceries"]
        assert project_bar(app).value == ""

    saved = TodoStore(store.path).load_projects()
    assert [project.name for project in saved] == ["groceries"]


async def test_a_project_can_be_made_before_it_has_any_todos(store):
    """It is a thing in its own right, not a word on a todo."""
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await enter_projects(pilot)
        await name_project(pilot, "groceries")

        assert app.todos == []
        assert len(app.projects) == 1


async def test_a_hash_typed_out_of_habit_is_not_part_of_the_name(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await enter_projects(pilot)
        await name_project(pilot, "#groceries")

        assert [project.name for project in app.projects] == ["groceries"]


async def test_a_name_of_two_words_is_refused(store):
    """A project you cannot type as a tag is a project half the app cannot reach."""
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await enter_projects(pilot)
        await name_project(pilot, "the big move")

        assert app.projects == []


async def test_the_same_name_twice_makes_one_project(store):
    store.save_projects([Project(name="groceries")])
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await enter_projects(pilot)
        await name_project(pilot, "GROCERIES")

        assert [project.name for project in app.projects] == ["groceries"]


# Choosing one


async def test_enter_on_a_project_shows_it_and_hands_the_focus_back_to_the_list(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")
        await add_todo(pilot, "walk dog")
        await show_project(pilot, "groceries")

        assert app.project is not None and app.project.name == "groceries"
        assert rows(app) == ["○  buy milk"]
        # You came through the pane on the way to the list, so that is where you end up.
        assert app.focused is app.query_one("#todos", ListView)


async def test_enter_on_all_gives_every_todo_back(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")
        await add_todo(pilot, "walk dog")
        await show_project(pilot, "groceries")
        await show_project(pilot, "All")

        assert app.project is None
        assert rows(app) == ["○  buy milk  #groceries", "○  walk dog"]


async def test_the_count_is_what_is_left_to_do(store):
    groceries = Project(name="groceries")
    store.save_projects([groceries])
    store.save(
        [
            Todo(text="buy milk", project_id=groceries.id),
            Todo(text="buy bread", done=True, project_id=groceries.id),
            Todo(text="walk dog"),
        ]
    )
    app = TaskyApp(store=store)

    async with app.run_test():
        # 2 left in the whole list, 1 left in groceries. The completed one counts
        # for neither: a project you have finished everything in should look finished.
        assert project_counts(app) == ["2", "1"]


# Changing one


async def test_alt_e_renames_a_project_everywhere_at_once(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")
        await stand_on_project(pilot, "groceries")
        await pilot.press("alt+e")
        await pilot.pause()

        assert project_bar(app).value == "groceries"

        await name_project(pilot, "shopping")

        assert [project.name for project in app.projects] == ["shopping"]
        # The todos point at it by id, so all of them are renamed by the one edit.
        assert rows(app) == ["○  buy milk  #shopping"]


async def test_the_highlight_stays_where_you_left_it(store):
    """The pane is redrawn for every count that changes, and a redraw must not move you."""
    store.save_projects([Project(name="groceries"), Project(name="health")])
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await stand_on_project(pilot, "health")
        rows_in_pane = app.query_one("#project-list", ListView)
        assert rows_in_pane.index == 2

        # A todo added two panes away changes what "All" counts, and so redraws this.
        await add_todo(pilot, "walk dog")

        assert rows_in_pane.index == 2

        await stand_on_project(pilot, "health")
        await pilot.press("alt+e")
        await pilot.pause()
        await name_project(pilot, "wellbeing")

        assert projects(app) == ["All", "groceries", "wellbeing"]
        assert rows_in_pane.index == 2  # not thrown back to the top of the pane


async def test_deleting_a_project_lands_you_on_the_next_one_down(store):
    store.save_projects([Project(name="groceries"), Project(name="health")])
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await stand_on_project(pilot, "groceries")
        await pilot.press("alt+d")
        await pilot.pause()

        assert projects(app) == ["All", "health"]
        assert app.query_one("#project-list", ListView).index == 1  # health


async def test_escape_leaves_a_rename_as_it_was(store):
    store.save_projects([Project(name="groceries")])
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await stand_on_project(pilot, "groceries")
        await pilot.press("alt+e")
        await pilot.pause()
        project_bar(app).value = "shopping"
        await pilot.press("escape")
        await pilot.pause()

        assert [project.name for project in app.projects] == ["groceries"]
        assert app.in_projects()  # escape backed out of the rename, not the pane


async def test_alt_d_deletes_the_project_and_unfiles_its_todos(store):
    """Deleting a project is filing your work differently, not throwing it away."""
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")
        await stand_on_project(pilot, "groceries")
        await pilot.press("alt+d")
        await pilot.pause()

        assert app.projects == []
        assert [todo.text for todo in app.todos] == ["buy milk"]
        assert app.todos[0].project_id is None
        assert rows(app) == ["○  buy milk"]


async def test_alt_z_puts_a_deleted_project_back_with_the_todos_it_held(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")
        await add_todo(pilot, "walk dog")
        await stand_on_project(pilot, "groceries")
        await pilot.press("alt+d")
        await pilot.pause()
        await pilot.press("alt+z")
        await pilot.pause()

        assert [project.name for project in app.projects] == ["groceries"]
        # Restored empty, it would be the name back and the filing gone.
        assert app.todos[0].project_id == app.projects[0].id
        assert app.todos[1].project_id is None  # and this one was never in it


async def test_deleting_the_project_you_are_standing_in_gives_the_whole_list_back(store):
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await add_todo(pilot, "buy milk #groceries")
        await add_todo(pilot, "walk dog")
        await show_project(pilot, "groceries")
        await stand_on_project(pilot, "groceries")
        await pilot.press("alt+d")
        await pilot.pause()

        assert app.project is None  # you cannot stand in a project that is not there
        assert rows(app) == ["○  buy milk", "○  walk dog"]


async def test_all_cannot_be_renamed_or_deleted(store):
    store.save_projects([Project(name="groceries")])
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await enter_projects(pilot)  # which lands on "All", the first row

        pane = app.projects_pane
        assert pane.check_action("edit", ()) is False
        assert pane.check_action("delete", ()) is False

        await pilot.press("alt+d")
        await pilot.pause()

        assert [project.name for project in app.projects] == ["groceries"]


# In the archive


async def test_the_pane_is_read_only_in_the_archive_but_still_shows_a_project(store):
    """Reading the archive a project at a time is worth doing. Rearranging it is not."""
    groceries = Project(name="groceries")
    store.save_projects([groceries])
    store.archive_completed(
        [
            Todo(text="buy milk", done=True, project_id=groceries.id),
            Todo(text="walk dog", done=True),
        ]
    )
    app = TaskyApp(store=store)

    async with app.run_test() as pilot:
        await pilot.press("alt+v")
        await pilot.pause()

        assert project_bar(app).disabled
        assert app.projects_pane.check_action("edit", ()) is False
        assert app.projects_pane.check_action("delete", ()) is False
        assert "read-only" in str(app.query_one("#project-status", Static).render())

        await show_project(pilot, "groceries")

        assert rows(app) == ["✓  buy milk"]
        assert app.sub_title == "archive · groceries"
