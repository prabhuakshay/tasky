from dataclasses import dataclass

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Label, ListView, Static

from tasky_tui import archive, status
from tasky_tui.notes import NotesDrawer
from tasky_tui.storage import Todo, TodoStore
from tasky_tui.widgets import ADD_PLACEHOLDER, EDIT_PLACEHOLDER, TodoInput, TodoItem


# The actions that act on the todo list -- and so the ones the app switches off while
# the focus is in the notes drawer, where the drawer's own alt+e, alt+d and alt+z act
# on the note you are standing on instead. Not "notes" (alt+n is how you get there
# from either pane) and not the rest of what the app answers for, which is Textual's
# rather than tasky's: tab to move the focus, the command palette, quitting. Those
# mean what they have always meant, wherever you are standing.
TODO_ACTIONS = frozenset(
    {"edit", "delete", "undo_delete", "cancel_edit"}
    | {"archive_completed", "unarchive", "toggle_archive_view"}
)


@dataclass(slots=True)
class Deleted:
    """A deleted todo, and enough about where it was to put it back."""

    todo: Todo
    index: int
    from_archive: bool


class TaskyApp(App[None]):
    """Tasky's terminal UI."""

    TITLE = "tasky"
    CSS_PATH = "app.tcss"

    # Three widths, because there are three things wanting the room and only the todo
    # itself always gets it (see app.tcss):
    #
    #   -narrow  under 60: no drawer beside the list -- alt+n puts it in front of the
    #            list instead, so the notes stay reachable in a terminal this size.
    #   -wide    the drawer, but not the date columns. Both would leave the todo a
    #            handful of characters, and the todo is the point.
    #   -roomy   room for all of it.
    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (60, "-wide"), (110, "-roomy")]

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
        Binding("alt+n", "notes", "Notes", priority=True),
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
        self.viewing_archive = False
        # The todo the input bar is currently editing, if it is editing one.
        self.editing: Todo | None = None
        # The last delete, kept so alt+z can put it back. One slot: undo is for
        # the delete you just regretted, not a history to walk backwards through.
        self.deleted: Deleted | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        # Two panes: the list, and the notes of whichever row of it is highlighted.
        # Each has a bar of its own to type into, so the bar you are in is always the
        # bar for the thing beside it.
        with Horizontal(id="body"):
            with Vertical(id="todo-pane"):
                # Also the editor: alt+e fills it with the highlighted todo. One bar
                # to type into, wherever the text is headed, rather than a second one
                # that is empty and in the way every moment you are not editing.
                yield TodoInput(placeholder=ADD_PLACEHOLDER, id="new-todo")
                # Naming the columns once, here, is what lets each row show bare dates
                # instead of repeating "added ..." and "done ..." on every line.
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
        await self.show(self.todos)
        self.query_one("#new-todo", TodoInput).focus()

    async def on_input_submitted(self, event: TodoInput.Submitted) -> None:
        text = event.value.strip()
        if not text:
            # Nothing typed is nothing to add. Mid-edit it is a mistake worth
            # saying out loud, since the alternative reading -- blank the todo --
            # is really a delete, and there is a key for that.
            if self.editing is not None:
                self.notify("A todo needs some text.", severity="warning")
            return

        if self.editing is not None:
            self._save_edit(text)
            return

        todo = Todo(text=text)
        self.todos.append(todo)
        todo_list = self.query_one("#todos", ListView)
        await todo_list.append(TodoItem(todo))
        self._ensure_highlight(todo_list)
        event.input.clear()
        self._persist()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if self.viewing_archive:
            # Completing an already-completed todo is meaningless. Restoring it
            # to the working list (alt+u) is the only edit the archive allows.
            return
        # TodoItem holds the same Todo object as self.todos, so toggling the
        # widget updates the list we are about to save.
        if isinstance(event.item, TodoItem):
            event.item.toggle_done()
            self._persist()

    def action_edit(self) -> None:
        if self.viewing_archive:
            # What is archived is what happened. Restore it (alt+u) to change it.
            return
        item = self.highlighted()
        if item is None:
            self.notify("Nothing to edit.", severity="warning")
            return

        self.editing = item.todo
        entry = self.query_one("#new-todo", TodoInput)
        entry.value = item.todo.text
        # Land at the end of the text, where you would be if you had just typed it.
        entry.cursor_position = len(entry.value)
        entry.placeholder = EDIT_PLACEHOLDER
        entry.add_class("editing")
        entry.focus()
        self.refresh_bindings()

    def action_notes(self) -> None:
        """Step across into the drawer, to write about the todo you are standing on."""
        if self.drawer.todo is None:
            self.notify("Nothing to write a note against.", severity="warning")
            return
        # A half-typed todo edit stays in the bar you left it in, and would be saved
        # by an enter you meant for a note. End it on the way out.
        self.end_edit()
        # Only means anything in a terminal too narrow to hold both panes, where it is
        # what puts the drawer in front of the list (see app.tcss). Wider, the drawer
        # is already there and this changes nothing.
        self.screen.add_class("-notes")
        self.drawer.focus_notes()

    async def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """The highlight moved, so the drawer is showing the notes of the wrong todo."""
        # The drawer's own list stops its highlights before they reach us, so this is
        # the todo list -- but say so anyway, rather than rely on it from a distance.
        if event.list_view.id != "todos":
            return
        todo = event.item.todo if isinstance(event.item, TodoItem) else None
        await self.drawer.show(todo, read_only=self.viewing_archive)

    def on_notes_drawer_changed(self, event: NotesDrawer.Changed) -> None:
        """A note was written, edited or deleted. Notes live in the todo, so save it."""
        self._persist()
        # The count in the todo's row is now one out.
        item = self._item_for(event.todo)
        if item is not None:
            item.refresh_todo()

    def on_notes_drawer_closed(self, event: NotesDrawer.Closed) -> None:
        """Escape, with no note edit left to back out of: the list wants you back."""
        self.screen.remove_class("-notes")
        self.query_one("#todos", ListView).focus()

    @property
    def drawer(self) -> NotesDrawer:
        return self.query_one(NotesDrawer)

    def in_drawer(self) -> bool:
        """Is the focus in the notes drawer? Which pane's keys apply turns on this."""
        focused = self.focused
        return focused is not None and self.drawer in focused.ancestors_with_self

    def action_cancel_edit(self) -> None:
        if self.editing is None:
            return
        self.notify(f"Left {self.editing.text!r} as it was.")
        self.end_edit()

    async def action_delete(self) -> None:
        # The highlight has not moved while you were editing, so this is the todo
        # in the input bar: drop the half-finished edit and delete what it named.
        self.end_edit()
        item = self.highlighted()
        if item is None:
            self.notify("Nothing to delete.", severity="warning")
            return

        todo = item.todo
        todo_list = self.query_one("#todos", ListView)

        if self.viewing_archive:
            self.store.delete_from_archive(todo)
            # index is where it sat in the working list, which this todo has none
            # of. Undo appends it back to the archive, so it never needs one.
            self.deleted = Deleted(todo=todo, index=0, from_archive=True)
        else:
            self.deleted = Deleted(
                todo=todo,
                index=self._position_of(todo),
                from_archive=False,
            )
            self.todos = [entry for entry in self.todos if entry is not todo]
            self.store.save(self.todos)

        # The row's position, not the todo's: in the archive view the two run in
        # opposite directions, and it is the row we are about to take out. A row is
        # highlighted -- _highlighted() just gave us the todo in it -- so it exists.
        row = todo_list.index or 0

        # pop() rather than a full redraw, so the highlight stays where you left
        # it and the next delete is the next todo down, not the top of the list.
        await todo_list.pop(row)
        self._ensure_highlight(todo_list)
        self._update_status(len(todo_list.children))
        self.refresh_bindings()
        self.notify(f"Deleted {todo.text!r} · alt+z to undo.")

    async def action_undo_delete(self) -> None:
        if self.deleted is None:
            self.notify("Nothing to undo.", severity="warning")
            return

        self.end_edit()
        deleted, self.deleted = self.deleted, None

        if deleted.from_archive:
            self.store.restore_to_archive(deleted.todo)
            if self.viewing_archive:
                await archive.show(self)
        else:
            self.todos.insert(deleted.index, deleted.todo)
            self._persist()
            if not self.viewing_archive:
                await self.show(self.todos)

        self.refresh_bindings()
        self.notify(f"Restored {deleted.todo.text!r}.")

    # The archive is a mode this list is in rather than a screen of its own, so the
    # keys are the app's. What they do is in archive.py.
    async def action_archive_completed(self) -> None:
        await archive.archive_completed(self)

    async def action_toggle_archive_view(self) -> None:
        await archive.toggle_view(self)

    async def action_unarchive(self) -> None:
        await archive.unarchive(self)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        # Standing in the drawer, alt+d is about the note you are on, not the todo the
        # notes are of. So the keys that act on the list switch off while the focus is
        # in there, and the drawer's own take the keys: Textual checks priority
        # bindings from the app downwards, and one that is switched off does not
        # swallow its key -- it carries on down the chain, to the drawer.
        #
        # Only those, and not everything the app answers for. tab is bound to the
        # app's own focus_next, and switching that off with the rest would make the
        # drawer a place you cannot tab out of.
        if self.in_drawer() and action in TODO_ACTIONS:
            return False

        # Restoring only means something in the archive, archiving and editing only
        # outside it, undo only with a delete behind you, and cancelling only with
        # an edit in front of you. Hide whichever does not apply, so the footer
        # offers the keys that would actually do something.
        if action == "unarchive":
            return self.viewing_archive
        if action in ("archive_completed", "edit"):
            return not self.viewing_archive
        if action == "undo_delete":
            return self.deleted is not None
        if action == "cancel_edit":
            return self.editing is not None
        return True

    def _save_edit(self, text: str) -> None:
        """Write the edited text back to the todo, and to disk."""
        assert self.editing is not None
        self.editing.text = text
        # created_at stays: editing the wording of a todo does not make it a new
        # one, and it was still added when it was added.
        item = self._item_for(self.editing)
        if item is not None:
            item.refresh_todo()
        self.end_edit()
        self._persist()

    def end_edit(self) -> None:
        """Hand the input bar back to adding todos. A no-op if it never left."""
        if self.editing is None:
            return
        self.editing = None
        entry = self.query_one("#new-todo", TodoInput)
        entry.clear()
        entry.placeholder = ADD_PLACEHOLDER
        entry.remove_class("editing")
        self.refresh_bindings()

    def highlighted(self) -> TodoItem | None:
        item = self.query_one("#todos", ListView).highlighted_child
        return item if isinstance(item, TodoItem) else None

    def _item_for(self, todo: Todo) -> TodoItem | None:
        # By identity, not by id: a hand-edited file can carry the same id twice,
        # and the row we want is the one holding this very object.
        return next((item for item in self.query(TodoItem) if item.todo is todo), None)

    def _position_of(self, todo: Todo) -> int:
        return next(i for i, entry in enumerate(self.todos) if entry is todo)

    async def show(self, todos: list[Todo]) -> None:
        """Put a list of todos in the list. The archive is one of the lists it shows."""
        todo_list = self.query_one("#todos", ListView)
        await todo_list.clear()
        await todo_list.extend(TodoItem(todo) for todo in todos)
        self._ensure_highlight(todo_list)
        self._update_status(len(todos))
        # Highlighted fires as the rows move under the cursor and keeps the drawer in
        # step, but it does not fire for a list that ends up empty -- and an empty list
        # is exactly when the drawer is showing the notes of a todo that is gone.
        item = self.highlighted()
        await self.drawer.show(
            item.todo if item else None,
            read_only=self.viewing_archive,
        )

    def _persist(self) -> None:
        self.store.save(self.todos)
        self._update_status(len(self.todos))

    def _update_status(self, shown: int) -> None:
        if self.viewing_archive:
            summary = status.archive(shown)
        else:
            completed = sum(todo.done for todo in self.todos)
            summary = status.working_list(len(self.todos) - completed, completed)
        self.query_one("#status", Static).update(summary)

    def _ensure_highlight(self, todo_list: ListView) -> None:
        # ListView only highlights a row automatically when it has children at
        # mount time. We add ours later, so without this the first Enter on a
        # freshly focused list would select nothing.
        if todo_list.index is None and len(todo_list.children):
            todo_list.index = 0
