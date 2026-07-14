"""Clearing the lot, and the screen that makes sure you meant to.

Its own file, like deleting and the archive: a command's worth of behaviour rather than
part of the shape of the app.

This is the one thing tasky does that it cannot take back. Everything else has a way
out -- a completed todo is struck through rather than gone, archiving is undone by
alt+u, and alt+z holds the delete you have just regretted. This has none, and so it has
to be the one thing tasky makes you say twice.

Twice, and in words. A yes/no box is one confident keystroke away from an empty tasky,
and the keystroke people are most confident about is the one they press without reading.
Typing "clear" cannot be done by muscle memory, because muscle memory has never done it
before -- and by the time you have typed five letters you have read the sentence above
them. That is the whole design: the delay is the point.

It is not on a key, either. It sits in the command palette (ctrl+p), where you have to
go looking for it and name it before it will happen. Nothing about clearing everything
should be reachable from the row of alt+keys your fingers already know: alt+d is one
slip from alt+c, and the two are not one slip apart in what they cost.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from tasky_tui import status
from tasky_tui.widgets import TodoInput

if TYPE_CHECKING:
    from tasky_tui.app import TaskyApp

CONFIRM_WORD = "clear"
"""What you have to type. Short enough to be no trouble, long enough to be no accident."""


class ConfirmClear(ModalScreen[bool]):
    """Asks whether you really meant it, and will not take a keystroke for an answer.

    Returns True only if the word was typed and the button pressed. Escape, the Cancel
    button, and any other way out all return False -- the safe answer is the one you get
    for doing nothing, which is the only sort of safe answer worth having.

    It is handed the sentence it shows rather than the todos it counts: what to say is
    text, and text is status.py's job, tested without a running app. The screen's job is
    to stand in the way.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, toll: str) -> None:
        super().__init__()
        self.toll = toll

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-clear"):
            yield Label("Clear everything?", id="confirm-title")
            # The count first, because it is the part that is about you rather than
            # about tasky, and the part most likely to stop you.
            yield Static(f"This deletes {self.toll}.", id="confirm-toll")
            yield Static(
                "Every todo, the notes written against them, everything you have "
                "archived, and every project. This cannot be undone: alt+z will not "
                "bring any of it back.",
                id="confirm-warning",
            )
            yield Label(f'Type "{CONFIRM_WORD}" to confirm:', id="confirm-prompt")
            # A TodoInput, not an Input: the app's alt+keys are priority bindings, so
            # they reach for a key before the focused widget does, and the ones we switch
            # off behind this screen would otherwise be typed into the box as letters.
            # This is the widget that already knows no alt+<letter> is ever text.
            yield TodoInput(placeholder=CONFIRM_WORD, id="confirm-word")
            with Horizontal(id="confirm-buttons"):
                yield Button("Cancel", id="cancel")
                # Disabled until the word is right, so the button cannot be the thing
                # you press before you have understood the sentence above it. variant
                # error, because it should not look like the button you reach for.
                yield Button("Clear it", id="clear", variant="error", disabled=True)

    def on_mount(self) -> None:
        self.query_one("#confirm-word", TodoInput).focus()

    # Every one of these stops its event, and the stopping is not housekeeping -- it is
    # the feature. A message from a widget climbs to the app unless something catches
    # it, and the app is listening: TodoInput.Submitted is how a todo gets added. Left
    # to climb, the enter that confirms this screen would also file the word "clear" as
    # a todo, in the list it is about to empty. The screen answers for its own bar.

    def on_input_changed(self, event: TodoInput.Changed) -> None:
        event.stop()
        self.query_one("#clear", Button).disabled = not self._word_is_right(event.value)

    def on_input_submitted(self, event: TodoInput.Submitted) -> None:
        # Enter in the box is the same answer as the button, and only when the button
        # would have been pressable. Enter on a half-typed word does nothing at all --
        # it does not cancel either, because you are plainly in the middle of answering.
        event.stop()
        if self._word_is_right(event.value):
            self.dismiss(True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "clear")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def _word_is_right(self, value: str) -> bool:
        # Case and stray spaces are not the test. The test is whether you typed the word
        # rather than reached for a key, and "Clear " passes that on any reading.
        return value.strip().lower() == CONFIRM_WORD


async def clear(app: TaskyApp) -> None:
    """Ask, and if the answer is really yes, start afresh."""
    # The palette is reachable from in front of the screen it opened, and a second
    # question stacked on the first is not a question anybody is answering.
    if isinstance(app.screen, ConfirmClear):
        return

    app.end_edit()
    # The one time the archive is read without being asked for. It is the only way to
    # say how much of it there is, and how much there is, is the warning.
    archived = app.store.load_archive()
    if not (app.todos or archived or app.projects):
        app.notify("Nothing to clear.", severity="warning")
        return

    toll = status.to_clear(
        todos=len(app.todos),
        notes=sum(len(todo.notes) for todo in (*app.todos, *archived)),
        archived=len(archived),
        projects=len(app.projects),
    )

    async def answered(confirmed: bool | None) -> None:
        # None is the screen going away without an answer, which is not a yes.
        if confirmed:
            await _start_afresh(app)

    await app.push_screen(ConfirmClear(toll), answered)


async def _start_afresh(app: TaskyApp) -> None:
    set_aside = app.store.clear_all()

    app.todos = []
    app.projects = []
    # Not just the data: the places you can be standing in it. A project you were inside
    # is gone, and so is the archive you may have been reading -- leaving the app in
    # either would be leaving you in a room that no longer exists.
    app.project = None
    app.viewing_archive = False
    # The undo slot is holding a todo that no longer exists anywhere. Empty it, or alt+z
    # would put one lone survivor back into a list you have just emptied on purpose.
    app.deleted = None

    await app.show(app.todos)
    await app.refresh_projects()
    app.refresh_sub_title()
    app.refresh_bindings()

    bar = app.query_one("#new-todo", TodoInput)
    # The archive is the one place tasky will not let you type a todo, and it says so by
    # disabling the bar (see archive.toggle_view). Clearing is leaving the archive
    # whether you were standing in it or not, so the bar has to be given back -- or you
    # would start afresh in front of a bar that will not take a word, and not be told why.
    bar.disabled = False
    # Wherever you were standing is gone, and the bar is where tasky starts.
    bar.focus()

    # Say where it went. The screen said this cannot be undone, and it cannot -- but a
    # person who has just realised what they did deserves to be told there is a rope,
    # even if pulling it is not something tasky will do for them.
    where = app.store.path.parent
    app.notify(
        f"Cleared everything. The old {status.plural(len(set_aside), 'file')} "
        f"can still be found in {where}, ending in .cleared.",
        timeout=10,
    )
