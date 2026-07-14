"""The notes of whichever todo is highlighted, in a drawer beside the list.

A todo is a line, and sometimes a line is not enough. The notes could have been a
screen of their own, but then reading them would mean leaving your list, and coming
back, and leaving again for the next todo -- when what you actually want is to run
down the list and see what you wrote about each one. So the drawer stays open, and
follows the highlight.

That makes the two panes two places to be, and a key has to mean something different
in each: alt+d deletes the todo you are on, or the note you are on, depending on
which pane you are standing in. The drawer binds those keys itself, and the app
switches its own off whenever the focus is in here (see TaskyApp.check_action) --
Textual checks priority bindings from the app downwards, and one that is switched off
does not swallow its key, so it carries on down the chain to this widget. The footer
follows the same rule, so it always offers the keys for the pane you are in.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, ListView, Static

from tasky_tui import status
from tasky_tui.storage import Note, Todo
from tasky_tui.widgets import (
    ADD_NOTE_PLACEHOLDER,
    EDIT_NOTE_PLACEHOLDER,
    NoteItem,
    TodoInput,
)

NO_TODO = "Notes"
"""The drawer's heading when there is no todo to be the notes of."""


@dataclass(slots=True)
class DeletedNote:
    """A deleted note, and where in the list it was, so alt+z can put it back."""

    note: Note
    index: int


class NotesDrawer(Vertical):
    """The notes of one todo: read them, write them, edit them, delete them."""

    BINDINGS = [
        Binding("alt+e", "edit", "Edit note", priority=True),
        Binding("alt+d", "delete", "Delete note", priority=True),
        Binding("alt+z", "undo_delete", "Undo delete", priority=True),
        # No character, so the bar never mistakes it for typing. It backs out of an
        # edit first, and only then out of the drawer, so a slip of the key cannot
        # throw away what you were part way through writing.
        Binding("escape", "cancel_edit", "Cancel edit"),
    ]

    class Changed(Message):
        """The notes of a todo have changed, and want writing to disk.

        The drawer edits the todo it was handed, in place. It does not know which
        list that todo is in, or which file the list is saved to -- so it says what
        happened, and leaves the saving to whoever does know.
        """

        def __init__(self, todo: Todo) -> None:
            super().__init__()
            self.todo = todo

    class Closed(Message):
        """Escape, with no edit left to back out of: the todo list wants the focus."""

    def __init__(self, id: str | None = None) -> None:
        super().__init__(id=id)
        # The todo whose notes are on show. None when the list is empty and there is
        # nothing to be the notes of.
        self.todo: Todo | None = None
        # The archive is a record of what happened, and the notes are part of it:
        # they can be read there, and not changed.
        self.read_only = False
        # The note the bar is currently editing, if it is editing one.
        self.editing: Note | None = None
        # One slot, like the todo list's: undo is for the delete you just regretted.
        self.deleted: DeletedNote | None = None

    def compose(self) -> ComposeResult:
        yield Static(NO_TODO, id="drawer-title", markup=False)
        yield TodoInput(placeholder=ADD_NOTE_PLACEHOLDER, id="new-note")
        yield ListView(id="note-list")
        yield Static(id="note-status")

    async def show(self, todo: Todo | None, read_only: bool = False) -> None:
        """Put a todo's notes in the drawer. The highlight moved, so this is the job."""
        # The edit and the undo both belonged to the todo you were looking at a
        # moment ago. Neither has anywhere to land now, so neither comes with us.
        self._end_edit()
        self.deleted = None

        self.todo = todo
        self.read_only = read_only
        self.query_one("#drawer-title", Static).update(todo.text if todo else NO_TODO)
        # Nothing to write a note against, or nothing you are allowed to write.
        self.query_one("#new-note", TodoInput).disabled = todo is None or read_only

        notes = self.query_one("#note-list", ListView)
        await notes.clear()
        if todo is not None:
            await notes.extend(NoteItem(note) for note in todo.notes)
        self._ensure_highlight(notes)
        self._update_status()
        self.app.refresh_bindings()

    def focus_notes(self) -> None:
        """Come into the drawer: at the bar, or at the notes if there is no writing."""
        entry = self.query_one("#new-note", TodoInput)
        if entry.disabled:
            self.query_one("#note-list", ListView).focus()
        else:
            entry.focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        # stop(), or it carries on up to the app, which would read it as a todo being
        # typed into the other bar.
        event.stop()
        if self.todo is None or self.read_only:
            return

        text = event.value.strip()
        if not text:
            # Nothing typed is nothing to add. Mid-edit it is worth saying out loud,
            # since the alternative reading -- blank the note -- is really a delete,
            # and there is a key for that.
            if self.editing is not None:
                self.notify("A note needs some text.", severity="warning")
            return

        if self.editing is not None:
            self._save_edit(text)
            return

        note = self.todo.add_note(text)
        notes = self.query_one("#note-list", ListView)
        await notes.append(NoteItem(note))
        self._ensure_highlight(notes)
        event.input.clear()
        self._changed()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Enter on a note opens it for editing, the way enter on a todo completes it:
        # the obvious thing to want from the row you are sitting on. A note has
        # nothing to complete, so editing is that thing.
        event.stop()
        if isinstance(event.item, NoteItem) and not self.read_only:
            self._edit(event.item)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        # The drawer's own list. The app watches the todo list, and would otherwise
        # take this for the highlight moving there and redraw the drawer underneath us.
        event.stop()

    def action_edit(self) -> None:
        item = self._highlighted()
        if item is None:
            self.notify("No note to edit.", severity="warning")
            return
        self._edit(item)

    async def action_delete(self) -> None:
        # The highlight has not moved while you were editing, so this is the note in
        # the bar: drop the half-finished edit and delete what it was editing.
        self._end_edit()
        item = self._highlighted()
        if item is None or self.todo is None:
            self.notify("No note to delete.", severity="warning")
            return

        note = item.note
        notes = self.query_one("#note-list", ListView)
        self.deleted = DeletedNote(note=note, index=self._position_of(note))
        self.todo.notes = [entry for entry in self.todo.notes if entry is not note]

        # pop() rather than a redraw, so the highlight stays where you left it and the
        # next delete is the next note down.
        await notes.pop(notes.index or 0)
        self._ensure_highlight(notes)
        self._changed()
        self.notify("Deleted the note · alt+z to undo.")

    async def action_undo_delete(self) -> None:
        if self.deleted is None or self.todo is None:
            self.notify("No note to restore.", severity="warning")
            return

        self._end_edit()
        deleted, self.deleted = self.deleted, None
        self.todo.notes.insert(deleted.index, deleted.note)

        notes = self.query_one("#note-list", ListView)
        await notes.insert(deleted.index, [NoteItem(deleted.note)])
        self._ensure_highlight(notes)
        self._changed()
        self.app.refresh_bindings()
        self.notify("Restored the note.")

    def action_cancel_edit(self) -> None:
        if self.editing is not None:
            self.notify("Left the note as it was.")
            self._end_edit()
            return
        # Nothing to back out of, so escape backs out of the drawer itself.
        self.post_message(self.Closed())

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        # What is archived is what happened; restore the todo (alt+u) to write more.
        # Undo only means something with a delete behind you. Escape always leaves,
        # whether it is leaving an edit or leaving the drawer.
        if action == "cancel_edit":
            return True
        if self.read_only or self.todo is None:
            return False
        if action == "undo_delete":
            return self.deleted is not None
        return True

    def _edit(self, item: NoteItem) -> None:
        """Open a note in the bar, with its text already in it."""
        self.editing = item.note
        entry = self.query_one("#new-note", TodoInput)
        entry.value = item.note.text
        # Land at the end of the text, where you would be if you had just typed it.
        entry.cursor_position = len(entry.value)
        entry.placeholder = EDIT_NOTE_PLACEHOLDER
        entry.add_class("editing")
        entry.focus()
        self.app.refresh_bindings()

    def _save_edit(self, text: str) -> None:
        """Write the edited text back to the note, and say so, so it gets saved."""
        assert self.editing is not None
        # set_text stamps updated_at: a note that has been rewritten says when. Its
        # created_at stays -- it is still the note you wrote when you wrote it.
        self.editing.set_text(text)
        item = self._item_for(self.editing)
        if item is not None:
            item.refresh_note()
        self._end_edit()
        self._changed()

    def _end_edit(self) -> None:
        """Hand the bar back to writing new notes. A no-op if it never left."""
        if self.editing is None:
            return
        self.editing = None
        entry = self.query_one("#new-note", TodoInput)
        entry.clear()
        entry.placeholder = ADD_NOTE_PLACEHOLDER
        entry.remove_class("editing")
        self.app.refresh_bindings()

    def _changed(self) -> None:
        """The notes are different from the ones on disk. Say so, and redraw the count."""
        assert self.todo is not None
        self._update_status()
        self.post_message(self.Changed(self.todo))

    def _highlighted(self) -> NoteItem | None:
        item = self.query_one("#note-list", ListView).highlighted_child
        return item if isinstance(item, NoteItem) else None

    def _item_for(self, note: Note) -> NoteItem | None:
        # By identity, not by id: a hand-edited file can carry the same id twice, and
        # the row we want is the one holding this very note.
        return next((item for item in self.query(NoteItem) if item.note is note), None)

    def _position_of(self, note: Note) -> int:
        assert self.todo is not None
        return next(i for i, entry in enumerate(self.todo.notes) if entry is note)

    def _update_status(self) -> None:
        count = len(self.todo.notes) if self.todo else 0
        summary = status.notes(count, self.read_only) if self.todo else ""
        self.query_one("#note-status", Static).update(summary)

    def _ensure_highlight(self, notes: ListView) -> None:
        # ListView only highlights a row by itself when it has children at mount time,
        # and ours always arrive later. Without this the first enter on a freshly
        # focused list would land on nothing.
        if notes.index is None and len(notes.children):
            notes.index = 0
