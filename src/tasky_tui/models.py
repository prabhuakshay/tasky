"""The three things tasky keeps: a todo, a note against it, and a project to file it in.

They are here rather than in storage.py because they are what the app passes around,
and only incidentally what it writes down. storage.py knows which file each of them
lives in and how a torn write is survived; this knows what they are.

Timestamps are stored as UTC ISO 8601 strings: unambiguous wherever the file is read,
and still legible to anyone who opens it in an editor. Every one of them is written
once and never invented -- a field we cannot honestly fill stays None, and the UI
shows nothing rather than a guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4


def _new_id() -> str:
    return uuid4().hex


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Note:
    """A note against a todo: what you found out, or what is left to do about it.

    updated_at is None until the note is edited, so a note nobody has touched has
    no edit date to show -- the same bargain completed_at makes on Todo below.
    """

    text: str
    id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_timestamp)
    updated_at: str | None = None

    def set_text(self, text: str) -> None:
        """Rewrite the note, stamping when it was rewritten."""
        self.text = text
        self.updated_at = _timestamp()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Note:
        return cls(
            text=str(data["text"]),
            id=str(data.get("id") or _new_id()),
            created_at=str(data.get("created_at") or _timestamp()),
            updated_at=str(data["updated_at"]) if data.get("updated_at") else None,
        )


@dataclass(slots=True)
class Project:
    """Something to file todos under: a name, and the day you first named it.

    A project is a thing in its own right rather than a word written on a todo, which
    is what lets it outlive the todos in it -- archive the last one and the project is
    still there to add to -- and what makes renaming it one edit rather than one edit
    per todo.

    The name is one word, so that it can be typed as ``#groceries`` on the end of a
    todo (see tags.py).
    """

    name: str
    id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_timestamp)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Project:
        return cls(
            name=str(data["name"]),
            id=str(data.get("id") or _new_id()),
            created_at=str(data.get("created_at") or _timestamp()),
        )


@dataclass(slots=True)
class Todo:
    """A single todo: any notes kept against it, and the project it is filed under.

    Notes are nested inside the todo rather than kept in a file of their own, because
    a note only means anything against the todo it belongs to. Nesting is what makes
    archiving a todo carry its notes along for free, and deleting one take them with
    it -- no second file to keep in step, and nothing left orphaned.

    A project is the other way about: named by id rather than nested, because it is
    one project and many todos, and because it goes on existing when the todos in it
    do not. project_id is None for a todo in no project, which is most of them --
    filing a todo is something you do when it helps, not a toll you pay on the way in.
    """

    text: str
    done: bool = False
    id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_timestamp)
    completed_at: str | None = None
    project_id: str | None = None
    notes: list[Note] = field(default_factory=list)

    def set_done(self, done: bool) -> None:
        """Complete or reopen the todo, keeping completed_at in step with done."""
        self.done = done
        self.completed_at = _timestamp() if done else None

    def add_note(self, text: str) -> Note:
        """Add a note, and hand it back to whoever wants to show it."""
        note = Note(text=text)
        self.notes.append(note)
        return note

    def file_under(self, project: Project | None) -> None:
        """Put the todo in a project, or -- with None -- take it out of the one it is in."""
        self.project_id = project.id if project is not None else None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Todo:
        """Build a Todo from stored JSON, filling in anything a hand-edit dropped.

        completed_at is the one field we cannot invent: a todo written by an older
        tasky is done without recording when, and stamping it now would be a
        fabrication. It stays None, and the UI simply shows no completion date.
        """
        return cls(
            text=str(data["text"]),
            done=bool(data.get("done", False)),
            id=str(data.get("id") or _new_id()),
            created_at=str(data.get("created_at") or _timestamp()),
            completed_at=str(data["completed_at"]) if data.get("completed_at") else None,
            # A todo from before projects existed is in none, which is a thing a todo
            # is perfectly entitled to be -- so there is nothing to invent here either.
            project_id=str(data["project_id"]) if data.get("project_id") else None,
            # A todo from before notes existed simply has none. asdict() writes the
            # nested notes back out, so no special handling is needed to save them.
            notes=[Note.from_dict(note) for note in data.get("notes") or []],
        )


def project_of(todo: Todo, projects: Iterable[Project]) -> Project | None:
    """The project a todo is filed under, if it is filed under one that still exists.

    A todo names its project by id, and the id can outlast the project: deleting a
    project unfiles the todos still in your list as it goes, but it cannot unfile the
    ones already archived -- the archive is the record of what happened, and we do not
    go back and rewrite it. So an id naming nothing is not damage; it is an archived
    todo remembering a project you have since thrown away. It shows no project, which
    is the truth: there is no longer one to show.
    """
    if todo.project_id is None:
        return None
    return next((project for project in projects if project.id == todo.project_id), None)


def project_named(name: str, projects: Iterable[Project]) -> Project | None:
    """Find a project by name, ignoring case, so #Groceries and #groceries are one."""
    folded = name.casefold()
    return next((project for project in projects if project.name.casefold() == folded), None)
