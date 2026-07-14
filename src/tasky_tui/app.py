from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from tasky_tui.storage import Todo, TodoStore


class TodoItem(ListItem):
    """One todo, rendered as a row in the list."""

    def __init__(self, todo: Todo) -> None:
        super().__init__()
        self.todo = todo

    def compose(self) -> ComposeResult:
        # markup=False, or Textual parses the "[x]" marker as a markup tag and eats it.
        yield Label(self._label(), markup=False)

    def on_mount(self) -> None:
        self.set_class(self.todo.done, "done")

    def toggle_done(self) -> None:
        self.todo.done = not self.todo.done
        self.query_one(Label).update(self._label())
        self.set_class(self.todo.done, "done")

    def _label(self) -> str:
        marker = "x" if self.todo.done else " "
        return f"[{marker}] {self.todo.text}"


class TaskyApp(App[None]):
    """Tasky's terminal UI."""

    TITLE = "tasky"
    CSS_PATH = "app.tcss"

    # priority=True, or these never fire while the Input has focus. Textual hands
    # Input an alt+<letter> event with .character set to the bare letter, so
    # Input._on_key sees a printable key, types it, and stops the event before it
    # can reach us. A priority binding is resolved before the focused widget.
    BINDINGS = [
        Binding("alt+a", "archive_completed", "Archive done", priority=True),
        Binding("alt+u", "unarchive", "Restore", priority=True),
        Binding("alt+v", "toggle_archive_view", "Archive", priority=True),
        Binding("alt+q", "quit", "Quit", priority=True),
    ]

    def __init__(self, store: TodoStore | None = None) -> None:
        super().__init__()
        self.store = store if store is not None else TodoStore()
        self.todos: list[Todo] = []
        self.viewing_archive = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="body"):
            yield Input(placeholder="What needs doing?", id="new-todo")
            yield ListView(id="todos")
            yield Static(id="status")
        yield Footer()

    async def on_mount(self) -> None:
        self.todos = self.store.load()
        await self._show(self.todos)
        self.query_one("#new-todo", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
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

    async def action_archive_completed(self) -> None:
        if self.viewing_archive:
            return
        completed = sum(todo.done for todo in self.todos)
        if not completed:
            self.notify("No completed todos to archive.", severity="warning")
            return

        self.todos = self.store.archive_completed(self.todos)
        await self._show(self.todos)
        self.notify(f"Archived {completed} completed {_todos(completed)}.")

    async def action_toggle_archive_view(self) -> None:
        self.viewing_archive = not self.viewing_archive
        self.sub_title = "archive" if self.viewing_archive else ""

        if self.viewing_archive:
            await self._show_archive()
        else:
            await self._show(self.todos)

        self.query_one("#new-todo", Input).disabled = self.viewing_archive
        if not self.viewing_archive:
            self.query_one("#new-todo", Input).focus()
        self.refresh_bindings()

    async def action_unarchive(self) -> None:
        if not self.viewing_archive:
            return
        item = self.query_one("#todos", ListView).highlighted_child
        if not isinstance(item, TodoItem):
            self.notify("Nothing to restore.", severity="warning")
            return

        self.todos = self.store.unarchive(item.todo, self.todos)
        await self._show_archive()
        self.notify(f"Restored {item.todo.text!r} to your list.")

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        # Restoring only means something in the archive, archiving only means
        # something outside it. Hide whichever does not apply.
        if action == "unarchive":
            return self.viewing_archive
        if action == "archive_completed":
            return not self.viewing_archive
        return True

    async def _show_archive(self) -> None:
        # Read the archive only now that it is being asked for, so startup never
        # pays for it however large it grows. Newest first.
        archived = self.store.load_archive()
        archived.reverse()
        await self._show(archived)

    async def _show(self, todos: list[Todo]) -> None:
        todo_list = self.query_one("#todos", ListView)
        await todo_list.clear()
        await todo_list.extend(TodoItem(todo) for todo in todos)
        self._ensure_highlight(todo_list)
        self._update_status(len(todos))

    def _persist(self) -> None:
        self.store.save(self.todos)
        self._update_status(len(self.todos))

    def _update_status(self, shown: int) -> None:
        if self.viewing_archive:
            if shown:
                summary = f"{shown} archived {_todos(shown)} · alt+u to restore one"
            else:
                summary = "Nothing archived yet · alt+v to go back"
        else:
            completed = sum(todo.done for todo in self.todos)
            summary = f"{len(self.todos) - completed} active"
            if completed:
                # Surface the backlog, so completed todos do not quietly pile up.
                summary += f" · {completed} completed (alt+a to archive)"
        self.query_one("#status", Static).update(summary)

    def _ensure_highlight(self, todo_list: ListView) -> None:
        # ListView only highlights a row automatically when it has children at
        # mount time. We add ours later, so without this the first Enter on a
        # freshly focused list would select nothing.
        if todo_list.index is None and len(todo_list.children):
            todo_list.index = 0


def _todos(count: int) -> str:
    return "todo" if count == 1 else "todos"
