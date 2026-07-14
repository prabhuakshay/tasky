from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Footer, Header, Label, ListView, Static

from tasky_tui import archive, deleting, editing, filing, status
from tasky_tui.deleting import Deleted
from tasky_tui.models import Project, Todo, project_of
from tasky_tui.notes import NotesDrawer
from tasky_tui.projects import ProjectsPane
from tasky_tui.storage import TodoStore
from tasky_tui.widgets import ADD_PLACEHOLDER, TodoInput, TodoItem

# The actions that act on the todo list -- and so the ones the app switches off while
# the focus is in one of the side panes, where alt+e, alt+d and alt+z belong to the
# note or the project you are standing on instead. Not "notes" or "projects" (alt+n
# and alt+p are how you reach a pane, from any of them), and not the rest of what the
# app answers for, which is Textual's rather than tasky's: tab to move the focus, the
# command palette, quitting. Those mean what they have always meant, wherever you are.
TODO_ACTIONS = frozenset(
    {"edit", "delete", "undo_delete", "cancel_edit", "move_to_project"}
    | {"archive_completed", "unarchive", "toggle_archive_view"}
)


class TaskyApp(App[None]):
    """Tasky's terminal UI."""

    TITLE = "tasky"
    CSS_PATH = "app.tcss"

    # Four widths, because there are four things wanting the room and only the todo
    # itself always gets it (see app.tcss). They give way from the right:
    #
    #   -narrow  under 60: neither side pane will stand beside a list this narrow --
    #            one of them would be a gutter. alt+n and alt+p put them in front of
    #            the list instead, so both stay reachable in a terminal this size.
    #   -wide    the notes drawer, which is the pane that is about the todo you are
    #            on, and so the one worth having open while you read down the list.
    #   -roomy   the projects pane as well.
    #   -full    room for the date columns too.
    #
    # The dates go first because they are a record and the todo is the point, and they
    # are the only one of the four you cannot ask for: alt+n and alt+p fetch a pane
    # wherever you are, and a todo wears its project on its own row.
    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (60, "-wide"), (100, "-roomy"), (130, "-full")]

    # priority=True, or these never fire while the input bar has focus. Textual
    # hands Input an alt+<letter> event with .character set to the bare letter, so
    # Input._on_key sees a printable key, types it, and stops the event before it
    # can reach us. A priority binding is resolved before the focused widget.
    #
    # That is only half of it. A binding check_action turns off does not consume
    # its key either, and the letter would still be typed -- see TodoInput, which
    # is the half that makes the shortcuts below safe to switch off.
    BINDINGS = [
        Binding("alt+e", "edit", "Edit", priority=True),
        Binding("alt+m", "move_to_project", "Move to project", priority=True),
        Binding("alt+n", "notes", "Notes", priority=True),
        Binding("alt+p", "projects", "Projects", priority=True),
        Binding("alt+d", "delete", "Delete", priority=True),
        Binding("alt+z", "undo_delete", "Undo delete", priority=True),
        Binding("alt+a", "archive_completed", "Archive done", priority=True),
        Binding("alt+u", "unarchive", "Restore", priority=True),
        Binding("alt+v", "toggle_archive_view", "Archive", priority=True),
        Binding("alt+q", "quit", "Quit", priority=True),
        # No character, so the Input never mistakes this one for typing.
        Binding("escape", "cancel_edit", "Cancel edit"),
    ]

    def __init__(self, store: TodoStore | None = None) -> None:
        super().__init__()
        self.store = store if store is not None else TodoStore()
        self.todos: list[Todo] = []
        self.projects: list[Project] = []
        # The project the list is showing, if it is showing one. None is all of them,
        # which is where you start and where "All" in the pane takes you back to.
        self.project: Project | None = None
        self.viewing_archive = False
        # The todo the input bar is currently editing, if it is editing one.
        self.editing: Todo | None = None
        # The last delete, kept so alt+z can put it back. One slot: undo is for
        # the delete you just regretted, not a history to walk backwards through.
        self.deleted: Deleted | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        # Three panes: the projects you file todos under, the list itself, and the
        # notes of whichever row of it is highlighted. Reading left to right, they run
        # from the widest thing to the narrowest -- a project, a todo, a note about it.
        # Each has a bar of its own to type into, so the bar you are in is always the
        # bar for the thing beside it.
        with Horizontal(id="body"):
            yield ProjectsPane(id="projects")
            with Vertical(id="todo-pane"):
                # Also the editor: alt+e fills it with the highlighted todo. One bar
                # to type into, wherever the text is headed, rather than a second one
                # that is empty and in the way every moment you are not editing.
                yield TodoInput(placeholder=ADD_PLACEHOLDER, id="new-todo")
                # Naming the columns once, here, is what lets each row show bare dates
                # instead of repeating "added ..." and "done ..." on every line. The
                # project has no column: it is written on the todo, where you typed it.
                with Horizontal(id="columns"):
                    yield Label("Todo", classes="text")
                    yield Label("Notes", classes="notes")
                    yield Label("Added", classes="date")
                    yield Label("Completed", classes="date")
                yield ListView(id="todos")
                yield Static(id="status")
            yield NotesDrawer(id="drawer")
        yield Footer()

    async def on_mount(self) -> None:
        self.todos = self.store.load()
        self.projects = self.store.load_projects()
        await self.show(self.todos)
        await self.refresh_projects()
        self.query_one("#new-todo", TodoInput).focus()

    # The bar you type into, and what a line typed in it means. In editing.py.
    async def on_input_submitted(self, event: TodoInput.Submitted) -> None:
        await editing.submit(self, event)

    def action_edit(self) -> None:
        editing.edit(self)

    def end_edit(self) -> None:
        editing.end(self)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self.viewing_archive:
            # Completing an already-completed todo is meaningless. Restoring it
            # to the working list (alt+u) is the only edit the archive allows.
            return
        # TodoItem holds the same Todo object as self.todos, so toggling the
        # widget updates the list we are about to save.
        if isinstance(event.item, TodoItem):
            event.item.toggle_done()
            self.persist()
            # A todo you just finished is one fewer left to do in its project.
            self.call_next(self.refresh_projects)

    def action_move_to_project(self) -> None:
        filing.move(self)

    def action_notes(self) -> None:
        """Step across into the drawer, to write about the todo you are standing on."""
        if self.drawer.todo is None:
            self.notify("Nothing to write a note against.", severity="warning")
            return
        # A half-typed todo edit stays in the bar you left it in, and would be saved
        # by an enter you meant for a note. End it on the way out.
        self.end_edit()
        # These only mean anything in a terminal too narrow to hold the panes beside
        # the list, where they are what puts one in front of it (see app.tcss). Wider,
        # the drawer is already there and this changes nothing.
        self.screen.remove_class("-projects")
        self.screen.add_class("-notes")
        self.drawer.focus_notes()

    async def action_projects(self) -> None:
        """Step across into the projects pane. What it does is in projects.py."""
        await filing.open_pane(self)

    async def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """The highlight moved, so the drawer is showing the notes of the wrong todo."""
        # The other panes stop their highlights before they reach us, so this is the
        # todo list -- but say so anyway, rather than rely on it from a distance.
        if event.list_view.id != "todos":
            return
        todo = event.item.todo if isinstance(event.item, TodoItem) else None
        await self.drawer.show(todo, read_only=self.viewing_archive)

    def on_notes_drawer_changed(self, event: NotesDrawer.Changed) -> None:
        """A note was written, edited or deleted. Notes live in the todo, so save it."""
        self.persist()
        # The count in the todo's row is now one out.
        item = self.item_for(event.todo)
        if item is not None:
            item.refresh_todo()

    def on_notes_drawer_closed(self, event: NotesDrawer.Closed) -> None:
        """Escape, with no note edit left to back out of: the list wants you back."""
        self.screen.remove_class("-notes")
        self.query_one("#todos", ListView).focus()

    async def on_projects_pane_selected(self, event: ProjectsPane.Selected) -> None:
        """The pane says which project to show. What that means is in filing.py."""
        await filing.selected(self, event.project)

    async def on_projects_pane_changed(self, event: ProjectsPane.Changed) -> None:
        """A project was made, renamed or deleted. Write it down, and redraw the rows."""
        await filing.changed(self)

    def on_projects_pane_closed(self, event: ProjectsPane.Closed) -> None:
        """Escape, with no rename left to back out of: the list wants you back."""
        self.screen.remove_class("-projects")
        self.query_one("#todos", ListView).focus()

    @property
    def drawer(self) -> NotesDrawer:
        return self.query_one(NotesDrawer)

    @property
    def projects_pane(self) -> ProjectsPane:
        return self.query_one(ProjectsPane)

    def in_drawer(self) -> bool:
        """Is the focus in the notes drawer?"""
        return self._standing_in(self.drawer)

    def in_projects(self) -> bool:
        """Is the focus in the projects pane?"""
        return self._standing_in(self.projects_pane)

    def in_side_pane(self) -> bool:
        """Is the focus in either of them? Which pane's keys apply turns on this."""
        return self.in_drawer() or self.in_projects()

    def _standing_in(self, pane: Widget) -> bool:
        focused = self.focused
        return focused is not None and pane in focused.ancestors_with_self

    def action_cancel_edit(self) -> None:
        if self.editing is None:
            return
        self.notify(f"Left {self.editing.text!r} as it was.")
        self.end_edit()

    # Deleting a todo, and the archive, are each a key's worth of behaviour rather than
    # part of the shape of the app. What they do is in deleting.py and archive.py.
    async def action_delete(self) -> None:
        await deleting.delete(self)

    async def action_undo_delete(self) -> None:
        await deleting.undo(self)

    async def action_archive_completed(self) -> None:
        await archive.archive_completed(self)

    async def action_toggle_archive_view(self) -> None:
        await archive.toggle_view(self)

    async def action_unarchive(self) -> None:
        await archive.unarchive(self)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        # Standing in a side pane, alt+d is about the note or the project you are on,
        # not the todo they belong to. So the keys that act on the list switch off while
        # the focus is in one, and the pane's own take the keys: Textual checks priority
        # bindings from the app downwards, and one that is switched off does not swallow
        # its key -- it carries on down the chain, to the pane.
        #
        # Only those, and not everything the app answers for. tab is bound to the app's
        # own focus_next, and switching that off with the rest would make the panes
        # places you cannot tab out of.
        if self.in_side_pane() and action in TODO_ACTIONS:
            return False

        # Restoring only means something in the archive, and archiving, editing and
        # filing only outside it; undo only with a delete behind you, and cancelling
        # only with an edit in front of you. Hide whichever does not apply, so the
        # footer offers the keys that would actually do something.
        if action == "unarchive":
            return self.viewing_archive
        if action in ("archive_completed", "edit", "move_to_project"):
            return not self.viewing_archive
        if action == "undo_delete":
            return self.deleted is not None
        if action == "cancel_edit":
            return self.editing is not None
        return True

    def shown(self) -> list[Todo]:
        """The todos the list is showing: all of them, or the ones in one project."""
        return filing.shown(self)

    def project_of(self, todo: Todo) -> Project | None:
        return project_of(todo, self.projects)

    def highlighted(self) -> TodoItem | None:
        item = self.query_one("#todos", ListView).highlighted_child
        return item if isinstance(item, TodoItem) else None

    def item_for(self, todo: Todo) -> TodoItem | None:
        # By identity, not by id: a hand-edited file can carry the same id twice,
        # and the row we want is the one holding this very object.
        return next((item for item in self.query(TodoItem) if item.todo is todo), None)

    def position_of(self, todo: Todo) -> int:
        return next(i for i, entry in enumerate(self.todos) if entry is todo)

    def row_for(self, todo: Todo) -> TodoItem:
        """A row for a todo, knowing what it is filed under and whether that is news."""
        return TodoItem(todo, self.project_of(todo), show_project=self.project is None)

    async def show(self, todos: list[Todo]) -> None:
        """Put a list of todos in the list. The archive is one of the lists it shows."""
        todo_list = self.query_one("#todos", ListView)
        await todo_list.clear()
        await todo_list.extend(self.row_for(todo) for todo in todos)
        self.ensure_highlight(todo_list)
        self.refresh_status(len(todos))
        # Highlighted fires as the rows move under the cursor and keeps the drawer in
        # step, but it does not fire for a list that ends up empty -- and an empty list
        # is exactly when the drawer is showing the notes of a todo that is gone.
        item = self.highlighted()
        await self.drawer.show(
            item.todo if item else None,
            read_only=self.viewing_archive,
        )

    async def refresh_projects(self) -> None:
        """Redraw the pane: what is left to do in each project has changed."""
        await self.projects_pane.show(
            self.projects,
            self.todos,
            self.project,
            read_only=self.viewing_archive,
        )

    def refresh_sub_title(self) -> None:
        """Say what the list is showing, when it is not simply your todos."""
        self.sub_title = status.viewing(
            self.viewing_archive,
            self.project.name if self.project else None,
        )

    def persist(self) -> None:
        self.store.save(self.todos)
        self.refresh_status(len(self.shown()))

    def refresh_status(self, shown: int) -> None:
        where = self.project.name if self.project else None
        if self.viewing_archive:
            summary = status.archive(shown, where)
        else:
            todos = self.shown()
            completed = sum(todo.done for todo in todos)
            summary = status.working_list(len(todos) - completed, completed, where)
        self.query_one("#status", Static).update(summary)

    def ensure_highlight(self, todo_list: ListView) -> None:
        # ListView only highlights a row automatically when it has children at
        # mount time. We add ours later, so without this the first Enter on a
        # freshly focused list would select nothing.
        if todo_list.index is None and len(todo_list.children):
            todo_list.index = 0
