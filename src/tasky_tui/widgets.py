"""The widgets tasky builds out of Textual's: a todo row, a note row, a project row,
and the bar you type into (which every pane uses, to add and to edit)."""

from datetime import datetime, timezone

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Label, ListItem

from tasky_tui import tags
from tasky_tui.models import Note, Project, Todo

ADD_PLACEHOLDER = "What needs doing?"
EDIT_PLACEHOLDER = "Edit the todo, then press enter — escape to cancel"
MOVE_PLACEHOLDER = "Name the project, then press enter — escape to cancel"
ADD_NOTE_PLACEHOLDER = "Add a note"
EDIT_NOTE_PLACEHOLDER = "Edit the note, then press enter — escape to cancel"
ADD_PROJECT_PLACEHOLDER = "Add a project"
EDIT_PROJECT_PLACEHOLDER = "Rename the project, then press enter — escape to cancel"

EVERY_TODO = "All"
"""The first row of the projects pane, which is not a project but the way out of one."""


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
    """One todo, as a row: what it is on the left, when it happened on the right.

    The row is handed its project rather than looking one up, because a row can see
    only itself, and a name is all it has to show. Whoever changes what a todo is
    filed under hands the row the new project and asks it to redraw -- the same deal
    the todo itself is on.
    """

    def __init__(
        self,
        todo: Todo,
        project: Project | None = None,
        show_project: bool = True,
    ) -> None:
        super().__init__()
        self.todo = todo
        self.project = project
        # A list that is one project already says so, in the pane and in the header, and
        # the tag would then repeat that word on every row of it. The project is still
        # here -- alt+e needs it, to hand the whole line back -- it is simply not worth
        # a word of the todo's width to say a thing you cannot help but know.
        self.show_project = show_project

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label(self._line(), classes="text")
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
        self.query_one(".text", Label).update(self._line())
        self.query_one(".notes", Label).update(self._notes())
        self.query_one(".completed", Label).update(self._completed())
        self.set_class(self.todo.done, "done")

    def _line(self) -> Text:
        """The todo, with the project it is filed under written where you typed it.

        On the end of the todo, not out in a column of its own. A column would be paid
        for out of the width of the todo by every list, including the many with no
        projects in them at all -- and it would stand the tag away from the text, in a
        ragged line down the screen, when the whole point of "#groceries" is that it is
        part of what you typed.

        A Text rather than markup: the todo is what the user wrote, so a todo that
        happens to contain "[dim]" has to come out as "[dim]" -- but the tag on the end
        of it is ours, and it can be dim without being marked up.
        """
        line = Text(f"{'✓' if self.todo.done else '○'}  {self.todo.text}")
        if self.project is not None and self.show_project:
            line.append(f"  {tags.MARKER}{self.project.name}", style="dim")
        return line

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


class ProjectItem(ListItem):
    """One project in the pane: its name, and how many todos are still open in it.

    project is None on the first row, which is not a project at all but every todo
    you have -- the way out of a project, and where the list starts before you have
    chosen one. It is a row rather than a key because it is a place you can be, and
    the pane should show you which place that is.
    """

    def __init__(self, project: Project | None, active: int) -> None:
        super().__init__()
        self.project = project
        self.active = active

    def compose(self) -> ComposeResult:
        with Horizontal():
            # markup=False: a project is named by a person, not written in markup.
            yield Label(self.name, markup=False, classes="text")
            yield Label(self._active(), classes="count")

    @property
    def name(self) -> str:
        return self.project.name if self.project else EVERY_TODO

    def _active(self) -> str:
        # What is left to do in it, not what is in it: a project you have finished
        # everything in should look finished, rather than as busy as the day you
        # started it. Nothing to do reads as nothing, for the same reason a todo
        # with no notes shows no count.
        return str(self.active) if self.active else ""


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
