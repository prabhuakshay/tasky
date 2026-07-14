"""Where todos, notes and projects are written, in the platform's user data directory.

What they are is models.py; this is the part that survives the power going out.

Three files, with different shapes because they have different jobs:

``todos.json``    The working list. Rewritten in full on every change, which is
                  cheap precisely because archiving keeps it small.
``archive.jsonl`` Completed todos, one JSON object per line. Append-only, so
                  archiving costs the same whether it holds ten todos or a
                  hundred thousand, and it is never read on startup. A torn
                  write damages a single line rather than the whole document.
``projects.json`` The projects a todo can be filed under. A file of their own,
                  because a project outlives the todos in it: archive the last
                  todo in a project and the project is still there to add to.
                  It could not live in either file above -- the working list is
                  the wrong place for something that survives the list emptying,
                  and archive.jsonl is append-only, so nothing in it can be
                  renamed. Written only when the projects themselves change,
                  which is rarely.

Notes went inside their todo; projects did not, and the difference is the whole
reason for the third file. A note means nothing apart from the todo it is about,
so nesting it costs nothing and buys everything -- archive the todo and the notes
go with it. A project means something with no todos in it at all.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from platformdirs import user_data_dir

from tasky_tui.models import Project, Todo

APP_NAME = "tasky"
DATA_DIR_ENV_VAR = "TASKY_DATA_DIR"
# 2 added completed_at, 3 added notes, 4 added the project a todo is filed under.
# All purely additive: a v1 file loads as a v4 one with no completion dates, no
# notes and no projects, and an older tasky reads a v4 file by ignoring the new
# fields -- it will show the todos, and simply not know they are filed anywhere.
SCHEMA_VERSION = 4


def _to_jsonl(todos: Iterable[Todo]) -> str:
    return "".join(json.dumps(asdict(todo)) + "\n" for todo in todos)


def data_dir() -> Path:
    """The directory todos live in, honouring a TASKY_DATA_DIR override."""
    override = os.environ.get(DATA_DIR_ENV_VAR)
    if override:
        return Path(override).expanduser()
    # appauthor=False keeps Windows at %LOCALAPPDATA%\tasky rather than ...\tasky\tasky.
    return Path(user_data_dir(APP_NAME, appauthor=False))


class TodoStore:
    """Loads and saves the working list, and archives completed todos."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else data_dir() / "todos.json"
        self.archive_path = self.path.with_name("archive.jsonl")
        self.projects_path = self.path.with_name("projects.json")

    @property
    def quarantine_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}.corrupt")

    @property
    def projects_quarantine_path(self) -> Path:
        return self.projects_path.with_name(f"{self.projects_path.name}.corrupt")

    def load(self) -> list[Todo]:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []

        try:
            document = json.loads(raw)
            entries = document["todos"]
            return [Todo.from_dict(entry) for entry in entries]
        except (json.JSONDecodeError, TypeError, KeyError):
            # The file exists but we cannot read it. Move it aside instead of
            # letting the next save overwrite whatever the user still has there.
            self.path.replace(self.quarantine_path)
            return []

    def save(self, todos: list[Todo]) -> None:
        document = {
            "version": SCHEMA_VERSION,
            "todos": [asdict(todo) for todo in todos],
        }
        self._write_atomically(self.path, json.dumps(document, indent=2))

    def load_projects(self) -> list[Project]:
        try:
            raw = self.projects_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []

        try:
            document = json.loads(raw)
            return [Project.from_dict(entry) for entry in document["projects"]]
        except (json.JSONDecodeError, TypeError, KeyError):
            # Same bargain as todos.json: move it aside rather than let the next
            # save overwrite whatever the user still has in there.
            self.projects_path.replace(self.projects_quarantine_path)
            return []

    def save_projects(self, projects: list[Project]) -> None:
        document = {
            "version": SCHEMA_VERSION,
            "projects": [asdict(project) for project in projects],
        }
        self._write_atomically(self.projects_path, json.dumps(document, indent=2))

    def archive_completed(self, todos: list[Todo], project: Project | None = None) -> list[Todo]:
        """Move completed todos into the archive. Returns the todos left behind.

        project narrows it to the completed todos filed under one project. The list
        you are looking at is the list alt+a acts on, and while it is showing a single
        project that is not all of them -- archiving todos you cannot see, because
        they are completed somewhere else, is not what the key looked like it did.
        """

        def swept(todo: Todo) -> bool:
            return todo.done and (project is None or todo.project_id == project.id)

        completed = [todo for todo in todos if swept(todo)]
        # Not "the active ones": a completed todo in another project stays exactly
        # where it was, and is still completed.
        remaining = [todo for todo in todos if not swept(todo)]
        if not completed:
            return remaining

        # Append first, then shrink the working list. If we crash in between, a
        # todo is archived but still in todos.json -- annoying but recoverable.
        # The other order would lose it outright.
        self._append_to_archive(completed)
        self.save(remaining)
        return remaining

    def unarchive(self, todo: Todo, active: list[Todo]) -> list[Todo]:
        """Bring an archived todo back to the working list. Returns the new list.

        The todo returns exactly as it was archived -- still completed -- so this
        is a true undo of archiving. Press enter on it to reopen it.

        Dropping an entry means rewriting the archive, which is the one operation
        that costs O(archive) rather than O(1). That is the price of keeping
        archive.jsonl honest: what is in the file is what is archived, so it stays
        readable with grep or jq. Unarchiving is a rare correction, whereas adding
        and archiving are not, so only the rare path pays.
        """
        remaining = [entry for entry in self.load_archive() if entry.id != todo.id]
        restored = [*active, todo]

        # Restore first, then drop from the archive. A crash in between leaves the
        # todo in both places -- visible twice, but not lost. The other order would
        # lose it outright.
        self.save(restored)
        self._rewrite_archive(remaining)
        return restored

    def delete_from_archive(self, todo: Todo) -> None:
        """Drop an archived todo for good.

        Like unarchive, this rewrites the file, for the same reason: what is in
        archive.jsonl is what is archived, so a deleted todo has to leave it.
        """
        self._rewrite_archive([entry for entry in self.load_archive() if entry.id != todo.id])

    def restore_to_archive(self, todo: Todo) -> None:
        """Put a deleted todo back in the archive, undoing delete_from_archive.

        It goes back by appending, so it lands at the end of the file and reads as
        the most recently archived todo. Rewriting the whole archive to slot it
        back into its old line would be a lot of work to preserve an ordering that
        only ever meant "the order things were archived in" anyway.
        """
        self._append_to_archive([todo])

    def load_archive(self) -> list[Todo]:
        """Read archived todos, newest last. Only needed to inspect the archive."""
        try:
            raw = self.archive_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []

        archived: dict[str, Todo] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                todo = Todo.from_dict(json.loads(line))
            except (json.JSONDecodeError, TypeError, KeyError):
                # A partial line from an interrupted append, or a bad hand-edit.
                # Skip it; the rest of the archive is still perfectly readable.
                continue
            # Keyed by id, so a todo archived twice (see archive_completed) is
            # only reported once.
            archived[todo.id] = todo
        return list(archived.values())

    def _rewrite_archive(self, todos: list[Todo]) -> None:
        if not todos:
            self.archive_path.unlink(missing_ok=True)
            return
        self._write_atomically(self.archive_path, _to_jsonl(todos))

    def _append_to_archive(self, todos: Iterable[Todo]) -> None:
        self.archive_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.archive_path, "a", encoding="utf-8") as handle:
            handle.write(_to_jsonl(todos))
            handle.flush()
            os.fsync(handle.fileno())

    def _write_atomically(self, path: Path, contents: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a sibling file and rename over the target, so an interrupted
        # save leaves the previous file intact rather than truncated.
        tmp = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        )
        try:
            with tmp:
                tmp.write(contents)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp.name, path)
        except BaseException:
            Path(tmp.name).unlink(missing_ok=True)
            raise
