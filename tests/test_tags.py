"""The #project on the end of a todo: what counts as one, and what does not."""

from tasky_tui import tags


def test_a_plain_todo_names_no_project():
    assert tags.split("buy milk") == ("buy milk", None)


def test_the_last_word_names_the_project():
    assert tags.split("buy milk #groceries") == ("buy milk", "groceries")


def test_only_the_last_word():
    """So a todo that has to carry a hash word has somewhere to put it."""
    assert tags.split("pay invoice #123 to acme") == ("pay invoice #123 to acme", None)


def test_a_hash_at_the_end_is_a_project_even_when_it_reads_as_a_number():
    """The price of a rule you can hold in your head. The row says so, and alt+e undoes it."""
    assert tags.split("pay invoice #123") == ("pay invoice", "123")


def test_a_bare_marker_names_no_project():
    """"buy milk #" is a project rubbed out, and means what never typing one means."""
    assert tags.split("buy milk #") == ("buy milk", None)


def test_a_tag_with_no_todo_leaves_no_todo():
    assert tags.split("#groceries") == ("", "groceries")


def test_surrounding_space_is_not_part_of_either():
    assert tags.split("  buy milk   #groceries  ") == ("buy milk", "groceries")


def test_join_puts_the_project_back_the_way_you_would_have_typed_it():
    assert tags.join("buy milk", "groceries") == "buy milk #groceries"
    assert tags.join("buy milk", None) == "buy milk"


def test_a_line_survives_the_round_trip():
    """What alt+e puts in the bar is what enter would read back out of it, unchanged."""
    for line in ("buy milk", "buy milk #groceries", "pay invoice #123 to acme"):
        text, name = tags.split(line)
        assert tags.split(tags.join(text, name)) == (text, name)


def test_open_for_starts_the_tag_without_filling_it_in():
    """What alt+m puts in the bar: a word and an enter, rather than nine backspaces."""
    assert tags.open_for("buy milk") == "buy milk #"
    assert tags.split(tags.open_for("buy milk")) == ("buy milk", None)
