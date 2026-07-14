import json

import pytest

from tasky_tui.storage import Todo, TodoStore


def test_archiving_moves_completed_out_of_the_working_list(store):
    store.save([Todo(text="buy milk", done=True), Todo(text="walk dog")])

    remaining = store.archive_completed(store.load())

    assert [todo.text for todo in remaining] == ["walk dog"]
    assert [todo.text for todo in store.load()] == ["walk dog"]
    assert [todo.text for todo in store.load_archive()] == ["buy milk"]


def test_archiving_with_nothing_completed_writes_no_archive(store):
    store.save([Todo(text="walk dog")])

    remaining = store.archive_completed(store.load())

    assert [todo.text for todo in remaining] == ["walk dog"]
    assert not store.archive_path.exists()


def test_archive_accumulates_across_calls(store):
    store.archive_completed([Todo(text="buy milk", done=True)])
    store.archive_completed([Todo(text="pay rent", done=True), Todo(text="walk dog")])

    assert [todo.text for todo in store.load_archive()] == ["buy milk", "pay rent"]
    assert [todo.text for todo in store.load()] == ["walk dog"]


def test_archive_is_one_json_object_per_line(store):
    store.archive_completed([Todo(text="buy milk", done=True), Todo(text="pay rent", done=True)])

    lines = store.archive_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    assert [json.loads(line)["text"] for line in lines] == ["buy milk", "pay rent"]


def test_archive_append_does_not_rewrite_existing_entries(store):
    """Appending is what keeps archiving O(new items) rather than O(archive)."""
    store.archive_completed([Todo(text="buy milk", done=True)])
    first_line = store.archive_path.read_text(encoding="utf-8").splitlines()[0]

    store.archive_completed([Todo(text="pay rent", done=True)])

    assert store.archive_path.read_text(encoding="utf-8").splitlines()[0] == first_line


def test_torn_line_in_archive_does_not_lose_the_rest(store):
    store.archive_completed([Todo(text="buy milk", done=True)])
    with open(store.archive_path, "a", encoding="utf-8") as handle:
        handle.write('{"text": "half-written')  # an interrupted append

    assert [todo.text for todo in store.load_archive()] == ["buy milk"]


def test_a_todo_archived_twice_is_reported_once(store):
    """A crash between the archive append and the save can leave a duplicate."""
    todo = Todo(text="buy milk", done=True)
    store.archive_completed([todo])
    store.archive_completed([todo])

    assert [archived.text for archived in store.load_archive()] == ["buy milk"]


def test_unarchive_moves_a_todo_back_to_the_working_list(store):
    store.save([Todo(text="buy milk", done=True), Todo(text="walk dog")])
    store.archive_completed(store.load())
    (archived,) = store.load_archive()

    active = store.unarchive(archived, store.load())

    assert [todo.text for todo in active] == ["walk dog", "buy milk"]
    assert [todo.text for todo in store.load()] == ["walk dog", "buy milk"]
    assert store.load_archive() == []


def test_unarchive_is_a_true_undo_of_archiving(store):
    original = [Todo(text="buy milk", done=True), Todo(text="walk dog")]
    store.save(original)

    store.archive_completed(store.load())
    (archived,) = store.load_archive()
    store.unarchive(archived, store.load())

    restored = {todo.id: todo for todo in store.load()}
    for todo in original:
        assert restored[todo.id].text == todo.text
        assert restored[todo.id].done == todo.done
        assert restored[todo.id].created_at == todo.created_at


def test_unarchive_leaves_the_other_archived_todos_alone(store):
    store.archive_completed([Todo(text="buy milk", done=True), Todo(text="pay rent", done=True)])
    milk, _rent = store.load_archive()

    store.unarchive(milk, [])

    assert [todo.text for todo in store.load_archive()] == ["pay rent"]


def test_unarchiving_the_last_todo_removes_the_archive_file(store):
    store.archive_completed([Todo(text="buy milk", done=True)])
    (archived,) = store.load_archive()

    store.unarchive(archived, [])

    assert not store.archive_path.exists()


def test_unarchive_writes_the_working_list_before_dropping_from_the_archive(store, monkeypatch):
    """A crash between the two writes must duplicate the todo, never lose it."""
    store.archive_completed([Todo(text="buy milk", done=True)])
    (archived,) = store.load_archive()

    def boom(self, todos):
        raise OSError("crash after saving, before rewriting the archive")

    monkeypatch.setattr(TodoStore, "_rewrite_archive", boom)

    with pytest.raises(OSError):
        store.unarchive(archived, [])

    monkeypatch.undo()
    assert [todo.text for todo in store.load()] == ["buy milk"]
    assert [todo.text for todo in store.load_archive()] == ["buy milk"]


def test_load_archive_is_empty_when_nothing_archived(store):
    assert store.load_archive() == []


def test_archiving_preserves_todo_fields(store):
    original = Todo(text="buy milk")
    original.set_done(True)

    store.archive_completed([original])

    (archived,) = store.load_archive()
    assert archived.id == original.id
    assert archived.created_at == original.created_at
    assert archived.completed_at == original.completed_at
    assert archived.done is True


def test_deleting_from_the_archive_drops_only_that_todo(store):
    store.archive_completed([Todo(text="buy milk", done=True), Todo(text="pay rent", done=True)])
    milk, rent = store.load_archive()

    store.delete_from_archive(milk)

    assert [todo.text for todo in store.load_archive()] == ["pay rent"]
    assert rent.id == store.load_archive()[0].id


def test_deleting_the_last_archived_todo_leaves_no_archive_behind(store):
    store.archive_completed([Todo(text="buy milk", done=True)])
    (archived,) = store.load_archive()

    store.delete_from_archive(archived)

    assert store.load_archive() == []
    assert not store.archive_path.exists()


def test_restoring_to_the_archive_brings_the_todo_back_whole(store):
    store.archive_completed([Todo(text="buy milk", done=True)])
    (archived,) = store.load_archive()
    store.delete_from_archive(archived)

    store.restore_to_archive(archived)

    (restored,) = store.load_archive()
    assert restored == archived


def test_deleting_from_the_archive_leaves_the_working_list_alone(store):
    store.save([Todo(text="walk dog")])
    store.archive_completed([Todo(text="buy milk", done=True), Todo(text="walk dog")])
    (archived,) = store.load_archive()

    store.delete_from_archive(archived)

    assert [todo.text for todo in store.load()] == ["walk dog"]
