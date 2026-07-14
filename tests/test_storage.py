import json

from tasky_tui.models import Note, Todo
from tasky_tui.storage import DATA_DIR_ENV_VAR, TodoStore, data_dir


def test_load_returns_empty_when_file_absent(store):
    assert store.load() == []


def test_todos_round_trip(store):
    store.save([Todo(text="buy milk"), Todo(text="walk dog", done=True)])

    loaded = store.load()

    assert [(todo.text, todo.done) for todo in loaded] == [
        ("buy milk", False),
        ("walk dog", True),
    ]


def test_save_preserves_ids_and_timestamps(store):
    original = Todo(text="buy milk")
    store.save([original])

    (loaded,) = store.load()

    assert loaded.id == original.id
    assert loaded.created_at == original.created_at


def test_completing_a_todo_records_when(store):
    todo = Todo(text="buy milk")
    assert todo.completed_at is None

    todo.set_done(True)
    store.save([todo])

    (loaded,) = store.load()
    assert loaded.done is True
    assert loaded.completed_at == todo.completed_at


def test_reopening_a_todo_clears_its_completion_date(store):
    todo = Todo(text="buy milk")
    todo.set_done(True)

    todo.set_done(False)
    store.save([todo])

    (loaded,) = store.load()
    assert loaded.done is False
    assert loaded.completed_at is None


def test_a_v1_file_loads_as_done_without_a_completion_date(store):
    """Older tasky files record no completion date, and we must not invent one."""
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text(
        json.dumps({"version": 1, "todos": [{"text": "buy milk", "done": True}]}),
        encoding="utf-8",
    )

    (loaded,) = store.load()

    assert loaded.done is True
    assert loaded.completed_at is None


def test_save_creates_missing_parent_directories(tmp_path):
    store = TodoStore(tmp_path / "nested" / "deeper" / "todos.json")

    store.save([Todo(text="buy milk")])

    assert store.path.exists()


def test_save_leaves_no_temp_files_behind(store):
    store.save([Todo(text="buy milk")])

    assert [path.name for path in store.path.parent.iterdir()] == ["todos.json"]


def test_corrupt_file_is_quarantined_rather_than_overwritten(store):
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text("{ this is not json", encoding="utf-8")

    assert store.load() == []
    assert not store.path.exists()
    assert store.quarantine_path.read_text(encoding="utf-8") == "{ this is not json"


def test_hand_edited_file_without_optional_fields_still_loads(store):
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text(
        json.dumps({"version": 1, "todos": [{"text": "buy milk"}]}), encoding="utf-8"
    )

    (loaded,) = store.load()

    assert loaded.text == "buy milk"
    assert loaded.done is False
    assert loaded.id
    assert loaded.created_at


def test_notes_round_trip(store):
    """Notes are nested inside their todo, so saving the todo saves them."""
    store.save([Todo(text="buy milk", notes=[Note(text="oat"), Note(text="soya")])])

    (loaded,) = store.load()

    assert [note.text for note in loaded.notes] == ["oat", "soya"]
    assert all(note.id and note.created_at for note in loaded.notes)


def test_a_rewritten_note_is_saved_with_both_its_dates(store):
    note = Note(text="oat")
    note.set_text("oat, not soya")
    store.save([Todo(text="buy milk", notes=[note])])

    (loaded,) = store.load()

    (saved,) = loaded.notes
    assert saved.created_at == note.created_at
    assert saved.updated_at == note.updated_at


def test_a_todo_saved_before_notes_existed_simply_has_none(store):
    """A v2 file, written by a tasky that had never heard of notes."""
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text(json.dumps({"version": 2, "todos": [{"text": "buy milk"}]}))

    (loaded,) = store.load()

    assert loaded.notes == []


def test_data_dir_honours_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv(DATA_DIR_ENV_VAR, str(tmp_path / "custom"))

    assert data_dir() == tmp_path / "custom"


def test_data_dir_defaults_to_platform_location(monkeypatch):
    monkeypatch.delenv(DATA_DIR_ENV_VAR, raising=False)

    assert data_dir().name == "tasky"
    assert data_dir().is_absolute()
