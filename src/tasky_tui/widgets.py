"""The two widgets tasky builds out of Textual's: a todo row, and the input bar."""

from datetime import datetime, timezone

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Label, ListItem

from tasky_tui.storage import Todo

ADD_PLACEHOLDER = "What needs doing?"
EDIT_PLACEHOLDER = "Edit the todo, then press enter — escape to cancel"


class TodoInput(Input):
    """The bar you type todos into, which knows a shortcut is not typing.

    A terminal sends alt+e as the letter "e" with a modifier attached, and Input
    types anything that arrives with a printable character. That is fine for the
    shortcuts the app acts on -- a priority binding beats the focused widget to
    the key -- but not for the ones it declines: alt+e in the archive, alt+z with
    nothing to undo, alt+u outside the archive. A declined binding never consumes
    its key (Textual's run_action returns False, and the event carries on down),
    so the letter would land in the bar as if you had typed it.

    No alt+<letter> is ever text, so none of them are typing.

    prevent_default rather than an early return, because Textual dispatches _on_key
    to every class in the MRO that defines one: returning would hand the key
    straight to Input._on_key, which is the thing that types it. The event is not
    stopped, only kept out of the text -- it still belongs to the app's bindings.
    """

    async def _on_key(self, event: events.Key) -> None:
        if event.key.startswith("alt+"):
            event.prevent_default()


class TodoItem(ListItem):
    """One todo, as a row: what it is on the left, when it happened on the right."""

    def __init__(self, todo: Todo) -> None:
        super().__init__()
        self.todo = todo

    def compose(self) -> ComposeResult:
        with Horizontal():
            # markup=False on the text, or a todo that happens to contain "[dim]"
            # would be parsed as markup instead of shown as the user typed it.
            yield Label(self._text(), markup=False, classes="text")
            yield Label(_when(self.todo.created_at), classes="date")
            yield Label(self._completed(), classes="date completed")

    def on_mount(self) -> None:
        self.set_class(self.todo.done, "done")

    def toggle_done(self) -> None:
        self.todo.set_done(not self.todo.done)
        self.refresh_todo()

    def refresh_todo(self) -> None:
        """Redraw the row from its todo, after the todo has changed underneath."""
        self.query_one(".text", Label).update(self._text())
        self.query_one(".completed", Label).update(self._completed())
        self.set_class(self.todo.done, "done")

    def _text(self) -> str:
        return f"{'✓' if self.todo.done else '○'}  {self.todo.text}"

    def _completed(self) -> str:
        # Ask the timestamp, not the flag: a todo completed by a tasky older than
        # this feature is done with no record of when, and the cell stays empty.
        return _when(self.todo.completed_at) if self.todo.completed_at else ""


def _when(timestamp: str) -> str:
    """Render a stored UTC timestamp in the reader's own timezone."""
    try:
        moment = datetime.fromisoformat(timestamp)
    except ValueError:
        # A hand-edited timestamp we cannot parse. Show it as it stands rather
        # than crashing the list over a cosmetic field.
        return timestamp
    if moment.tzinfo is None:
        # Naive timestamps only reach us from a hand-edit; ours are always UTC.
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone().strftime("%d %b %H:%M")
