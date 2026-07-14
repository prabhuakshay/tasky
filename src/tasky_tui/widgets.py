"""The widgets tasky builds out of Textual's: a todo row, a note row, and the bar
you type into (which both screens use, to add and to edit)."""

from datetime import datetime, timezone

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Label, ListItem

from tasky_tui.storage import Note, Todo

ADD_PLACEHOLDER = "What needs doing?"
EDIT_PLACEHOLDER = "Edit the todo, then press enter — escape to cancel"
ADD_NOTE_PLACEHOLDER = "Add a note"
EDIT_NOTE_PLACEHOLDER = "Edit the note, then press enter — escape to cancel"


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
            yield Label(self._notes(), classes="notes")
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
        self.query_one(".notes", Label).update(self._notes())
        self.query_one(".completed", Label).update(self._completed())
        self.set_class(self.todo.done, "done")

    def _text(self) -> str:
        return f"{'✓' if self.todo.done else '○'}  {self.todo.text}"

    def _notes(self) -> str:
        # A count, not the notes themselves: the row says a todo has more to it,
        # and alt+n is how you read it. A todo with nothing written against it
        # says nothing, rather than a nought down the whole list.
        return f"✎ {len(self.todo.notes)}" if self.todo.notes else ""

    def _completed(self) -> str:
        # Ask the timestamp, not the flag: a todo completed by a tasky older than
        # this feature is done with no record of when, and the cell stays empty.
        return _when(self.todo.completed_at) if self.todo.completed_at else ""


class NoteItem(ListItem):
    """One note: what it says, and underneath in smaller print, when it was written.

    Under, not beside. A todo is a line and its dates sit in columns beside it, but a
    note is a paragraph in a drawer a third the width of the screen -- there is no
    room out to the right, and taking it from the note would be taking it from the
    thing you came to read.
    """

    def __init__(self, note: Note) -> None:
        super().__init__()
        self.note = note

    def compose(self) -> ComposeResult:
        # markup=False for the same reason as a todo: a note is text, not markup.
        yield Label(self.note.text, markup=False, classes="text")
        yield Label(self._when_line(), classes="when")

    def refresh_note(self) -> None:
        """Redraw the row from its note, after the note has changed underneath."""
        self.query_one(".text", Label).update(self.note.text)
        self.query_one(".when", Label).update(self._when_line())

    def _when_line(self) -> str:
        written = _when(self.note.created_at)
        # The edit only shows once there has been one. "Written, and never touched
        # since" is worth being able to see, and a note is not "edited" on the day it
        # was written -- the same bargain the completed column makes on a todo.
        if self.note.updated_at:
            return f"{written} · edited {_when(self.note.updated_at)}"
        return written


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
