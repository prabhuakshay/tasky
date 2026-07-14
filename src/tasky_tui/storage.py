"""Persistence for todos, in the platform's user data directory.

Two files, with different shapes because they have different jobs:

``todos.json``    The working list. Rewritten in full on every change, which is
                  cheap precisely because archiving keeps it small.
``archive.jsonl`` Completed todos, one JSON object per line. Append-only, so
                  archiving costs the same whether it holds ten todos or a
                  hundred thousand, and it is never read on startup. A torn
                  write damages a single line rather than the whole document.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from platformdirs import user_data_dir

APP_NAME = "tasky"
DATA_DIR_ENV_VAR = "TASKY_DATA_DIR"
# 2 added completed_at. Purely additive: a v1 file loads as a v2 one with no
# completion dates, and an older tasky reads a v2 file by ignoring the new field.
SCHEMA_VERSION = 2


def _new_id() -> str:
    return uuid4().hex


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class Todo:
    """A single todo.

    Timestamps are stored as UTC ISO 8601 strings: unambiguous wherever the file
    is read, and still legible to anyone who opens todos.json in an editor.
    """

    text: str
    done: bool = False
    id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_timestamp)
    completed_at: str | None = None

    def set_done(self, done: bool) -> None:
        """Complete or reopen the todo, keeping completed_at in step with done."""
        self.done = done
        self.completed_at = _timestamp() if done else None

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
        )


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

    @property
    def quarantine_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}.corrupt")

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

    def archive_completed(self, todos: list[Todo]) -> list[Todo]:
        """Move completed todos into the archive. Returns the todos left behind."""
        completed = [todo for todo in todos if todo.done]
        active = [todo for todo in todos if not todo.done]
        if not completed:
            return active

        # Append first, then shrink the working list. If we crash in between, a
        # todo is archived but still in todos.json -- annoying but recoverable.
        # The other order would lose it outright.
        self._append_to_archive(completed)
        self.save(active)
        return active

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
