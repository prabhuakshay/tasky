"""The projects you file todos under, in a pane down the left of the list.

A third pane, and the same bargain as the notes drawer on the other side: it is a
place you can stand, so the keys you already know mean the thing in front of you --
alt+e renames the project you are on, alt+d deletes it, alt+z puts it back. The app
switches its own copies of those keys off while the focus is in here (see
TaskyApp.check_action), which is what lets three panes share three keys without any
of them being a surprise.

Where the drawer follows the highlight -- it is a view of the todo you are on, so it
has no choice -- this pane does not. It is a control rather than a view: you walk down
it, and the list only changes when you press enter on a project. The focus goes back
to the list when you do, because choosing a project is something you do on the way to
working in it.

The first row is "All", which is not a project. It is the way back out of one, and
having it there means the pane can show you which of the two you are in, rather than
leaving you to work it out from the list looking shorter than you remember.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, ListView, Static

from tasky_tui import status, tags
from tasky_tui.models import Project, Todo, project_named
from tasky_tui.widgets import (
    ADD_PROJECT_PLACEHOLDER,
    EDIT_PROJECT_PLACEHOLDER,
    EVERY_TODO,
    ProjectItem,
    TodoInput,
)

TITLE = "Projects"
NOT_A_PROJECT = f"{EVERY_TODO} is every todo, not a project."
ONE_WORD = "A project name is one word, so you can type it as #groceries."


@dataclass(slots=True)
class DeletedProject:
    """A deleted project, and enough about it to put it back.

    todos is what it held, which the delete unfiled. They are why a deleted project
    cannot simply be appended back on: restoring it means restoring the filing, and
    the delete is the only thing that still knows what was in it.
    """

    project: Project
    index: int
    todos: list[Todo]


class ProjectsPane(Vertical):
    """The projects: make them, rename them, delete them, and show one at a time."""

    BINDINGS = [
        Binding("alt+e", "edit", "Rename project", priority=True),
        Binding("alt+d", "delete", "Delete project", priority=True),
        Binding("alt+z", "undo_delete", "Undo delete", priority=True),
        # No character, so the bar never mistakes it for typing. It backs out of a
        # rename first and only then out of the pane, so a slip of the key cannot
        # throw away what you were part way through typing.
        Binding("escape", "cancel_edit", "Cancel edit"),
    ]

    class Selected(Message):
        """Show me this project -- or, with None, show me all of them again."""

        def __init__(self, project: Project | None) -> None:
            super().__init__()
            self.project = project

    class Changed(Message):
        """The projects have changed, and want writing to disk.

        The pane edits the lists it was handed, in place. It does not know which files
        they are saved to, or what the todo list is showing -- so it says what happened
        and leaves the rest to whoever does know.
        """

    class Closed(Message):
        """Escape, with no rename left to back out of: the todo list wants the focus."""

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        # The app's own lists, edited in place. The pane needs the todos as well as the
        # projects, because deleting a project is something that happens to the todos
        # in it as much as to the project itself.
        self.projects: list[Project] = []
        self.todos: list[Todo] = []
        # The project the todo list is showing, if it is showing one. Not the
        # highlight: you can walk past a project without going into it.
        self.current: Project | None = None
        # Projects belong to the working list, not to the archive. Reading the archive
        # a project at a time is worth doing; rearranging your projects from inside a
        # record of what happened is not.
        self.read_only = False
        # The project the bar is currently renaming, if it is renaming one.
        self.editing: Project | None = None
        # One slot, like the list's and the drawer's: undo is for the delete you just
        # regretted, not a history to walk backwards through.
        self.deleted: DeletedProject | None = None

    def compose(self) -> ComposeResult:
        yield Static(TITLE, id="projects-title")
        yield TodoInput(placeholder=ADD_PROJECT_PLACEHOLDER, id="new-project")
        yield ListView(id="project-list")
        yield Static(id="project-status")

    async def show(
        self,
        projects: list[Project],
        todos: list[Todo],
        current: Project | None,
        read_only: bool = False,
    ) -> None:
        """Redraw the pane: every project, and what is left to do in each of them."""
        self._end_edit()
        self.projects = projects
        self.todos = todos
        self.current = current
        self.read_only = read_only
        self.query_one("#new-project", TodoInput).disabled = read_only

        rows = self.query_one("#project-list", ListView)
        # The pane is redrawn for anything that changes a count -- which is every todo
        # you add, finish or throw away -- and clearing a ListView drops its highlight.
        # Without putting it back, renaming a project would send you to the top of the
        # pane, and so would completing a todo two panes away.
        standing_on = rows.index
        await rows.clear()
        # "All" first, and it is not one of them: None is the row, and the row is the
        # way out of a project rather than another project to be in.
        await rows.extend(
            ProjectItem(project, self._active_in(project)) for project in (None, *projects)
        )
        if standing_on is not None and len(rows.children):
            # Clamped, because the row you were standing on is the one you may have just
            # deleted -- in which case you land on the next project down, the way you do
            # in the list and in the drawer.
            rows.index = min(standing_on, len(rows.children) - 1)
        self._mark_current()
        self._ensure_highlight(rows)
        self._update_status()
        self.app.refresh_bindings()

    def focus_projects(self) -> None:
        """Come into the pane, at the projects: choosing one is what you came to do.

        Not at the bar, which is where the drawer puts you -- and the difference is the
        difference between the two panes. You go to the notes to write one, and there
        is a project on the end of every todo you type, so you rarely come here to make
        one: you come to stand in one. Landing in the bar would mean an arrow key that
        goes nowhere and a tab you have to know about before the pane does anything.

        With no projects yet there is nothing to choose between, so the only thing you
        can have come for is to make one, and the bar is where you land.
        """
        entry = self.query_one("#new-project", TodoInput)
        if not self.projects and not entry.disabled:
            entry.focus()
            return
        self.query_one("#project-list", ListView).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        # stop(), or it carries on up to the app, which would read it as a todo typed
        # into a different bar.
        event.stop()
        if self.read_only:
            return

        name = self._name_in(event.value)
        if name is None:
            return

        if self.editing is not None:
            await self._save_rename(name)
            return

        if project_named(name, self.projects) is not None:
            self.notify(f"There is already a project called {name!r}.", severity="warning")
            return

        self.projects.append(Project(name=name))
        event.input.clear()
        await self._changed()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Enter on a project shows it, the way enter on a todo completes it: the
        # obvious thing to want from the row you are sitting on.
        event.stop()
        if isinstance(event.item, ProjectItem):
            self.current = event.item.project
            self._mark_current()
            self.post_message(self.Selected(event.item.project))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        # The pane's own list. The app watches the todo list, and would otherwise take
        # this for the highlight moving there and redraw the drawer underneath us.
        event.stop()
        # Whether alt+e and alt+d do anything depends on the row you are on, so the
        # footer has to be asked again every time the highlight moves.
        self.app.refresh_bindings()

    def action_edit(self) -> None:
        project = self._highlighted()
        if project is None:
            self.notify(NOT_A_PROJECT, severity="warning")
            return

        self.editing = project
        entry = self.query_one("#new-project", TodoInput)
        entry.value = project.name
        # Land at the end of the name, where you would be if you had just typed it.
        entry.cursor_position = len(entry.value)
        entry.placeholder = EDIT_PROJECT_PLACEHOLDER
        entry.add_class("editing")
        entry.focus()
        self.app.refresh_bindings()

    async def action_delete(self) -> None:
        # The highlight has not moved while you were renaming, so this is the project
        # in the bar: drop the half-finished rename and delete what it named.
        self._end_edit()
        project = self._highlighted()
        if project is None:
            self.notify(NOT_A_PROJECT, severity="warning")
            return

        # The todos go on existing; they are simply in no project any more. Deleting a
        # project is filing your work differently, not throwing it away -- and alt+d on
        # the todos themselves is right there if throwing it away is what you meant.
        emptied = [todo for todo in self.todos if todo.project_id == project.id]
        for todo in emptied:
            todo.file_under(None)

        self.deleted = DeletedProject(
            project=project,
            index=self.projects.index(project),
            todos=emptied,
        )
        self.projects.remove(project)

        # You cannot stand in a project that is not there any more, so the list goes
        # back to showing everything -- with the todos that were in it still in it.
        if self.current is project:
            self.current = None
            self.post_message(self.Selected(None))

        await self._changed()
        self.notify(f"Deleted the project {project.name!r} · alt+z to undo.")

    async def action_undo_delete(self) -> None:
        if self.deleted is None:
            self.notify("No project to restore.", severity="warning")
            return

        self._end_edit()
        deleted, self.deleted = self.deleted, None
        self.projects.insert(deleted.index, deleted.project)
        # Back where it was, with the todos it had. A project restored empty would be
        # the name back and the filing gone, which is the half of it nobody wanted.
        for todo in deleted.todos:
            todo.file_under(deleted.project)

        await self._changed()
        self.notify(f"Restored the project {deleted.project.name!r}.")

    def action_cancel_edit(self) -> None:
        if self.editing is not None:
            self.notify("Left the project as it was.")
            self._end_edit()
            return
        # Nothing to back out of, so escape backs out of the pane itself.
        self.post_message(self.Closed())

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        # Escape always leaves, whether it is leaving a rename or leaving the pane.
        if action == "cancel_edit":
            return True
        if self.read_only:
            return False
        if action == "undo_delete":
            return self.deleted is not None
        if action in ("edit", "delete"):
            # "All" is every todo you have, not a project: no name to change, nothing
            # to delete. The footer stops offering the keys as you land on it, rather
            # than offering them and then declining.
            return self._highlighted() is not None
        return True

    def _name_in(self, value: str) -> str | None:
        """The project name in what was typed, if what was typed is a name at all."""
        # A "#groceries" typed out of habit is someone naming a project, so take the
        # marker off -- rather than make a project whose name begins with a hash and
        # could never afterwards be typed as a tag.
        name = value.strip().removeprefix(tags.MARKER).strip()
        if not name:
            # Nothing typed is nothing to add. Mid-rename it is worth saying out loud,
            # since the alternative reading -- blank the name -- is really a delete,
            # and there is a key for that.
            if self.editing is not None:
                self.notify("A project needs a name.", severity="warning")
            return None
        if " " in name:
            # The tag on the end of a todo is one word, and a project you cannot type
            # is a project that half the app cannot reach.
            self.notify(ONE_WORD, severity="warning")
            return None
        return name

    async def _save_rename(self, name: str) -> None:
        """Write the new name back to the project, and say so, so it gets saved."""
        assert self.editing is not None
        clash = project_named(name, self.projects)
        if clash is not None and clash is not self.editing:
            self.notify(f"There is already a project called {name!r}.", severity="warning")
            return

        # The todos in it point at it by id, so this renames it on every one of them at
        # once -- which is the whole reason a project is a thing and not a word.
        self.editing.name = name
        self._end_edit()
        await self._changed()

    def _end_edit(self) -> None:
        """Hand the bar back to making new projects. A no-op if it never left."""
        if self.editing is None:
            return
        self.editing = None
        entry = self.query_one("#new-project", TodoInput)
        entry.clear()
        entry.placeholder = ADD_PROJECT_PLACEHOLDER
        entry.remove_class("editing")
        self.app.refresh_bindings()

    async def _changed(self) -> None:
        """The projects are not the ones on disk. Redraw the pane, and say so."""
        await self.show(self.projects, self.todos, self.current, self.read_only)
        self.post_message(self.Changed())

    def _active_in(self, project: Project | None) -> int:
        """What is still to do in a project -- or, for "All", in the whole list."""
        return sum(
            not todo.done and (project is None or todo.project_id == project.id)
            for todo in self.todos
        )

    def _highlighted(self) -> Project | None:
        """The project the highlight is on. None on "All", which is not one."""
        item = self.query_one("#project-list", ListView).highlighted_child
        return item.project if isinstance(item, ProjectItem) else None

    def _mark_current(self) -> None:
        for item in self.query(ProjectItem):
            item.set_class(item.project is self.current, "-current")

    def _update_status(self) -> None:
        summary = status.projects(len(self.projects), self.read_only)
        self.query_one("#project-status", Static).update(summary)

    def _ensure_highlight(self, rows: ListView) -> None:
        # ListView only highlights a row by itself when it has children at mount time,
        # and ours always arrive later. Without this the first enter on a freshly
        # focused pane would land on nothing.
        if rows.index is None and len(rows.children):
            rows.index = 0
