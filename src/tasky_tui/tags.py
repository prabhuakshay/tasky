"""The ``#project`` on the end of a todo, as you type it.

There is no separate box to name a project in, because there is no separate box for
anything here: you type a todo, and if the last word of it starts with a ``#``, that
word is the project it goes in. The rest of the line is the todo.

Only the last word is looked at, and that is the whole rule. "pay invoice #123 to
acme" is a todo about an invoice and nothing else, because the hash is not at the end
-- so a todo that really must carry a hash word has somewhere to put it. "pay invoice
#123" does file itself under a project called 123, which is the price of a rule you
can hold in your head, and it is not a trap: the project shows on the row, alt+e hands
you back the very line you typed, and deleting the tag takes the todo back out again.

That round trip is what makes the tag safe to be the whole truth. What is in the bar
is what the todo is: no tag means no project, whether you never typed one or you have
just rubbed it out. Nothing is remembered behind your back.
"""

MARKER = "#"


def split(line: str) -> tuple[str, str | None]:
    """Split a typed line into the todo, and the project it files itself under.

    The name is None when the line names no project -- including "buy milk #", which
    is a line that has had its project deliberately rubbed out, and means the same
    thing as never having typed one.
    """
    line = line.strip()
    before, _, last = line.rpartition(" ")
    if not last.startswith(MARKER):
        return line, None
    return before.strip(), last[len(MARKER) :].strip() or None


def join(text: str, name: str | None) -> str:
    """Put the project back on the end of the todo, the way you would have typed it.

    The inverse of split(), and the reason editing a todo cannot silently unfile it:
    alt+e fills the bar with what split() would give back unchanged.
    """
    return f"{text} {MARKER}{name}" if name else text


def open_for(text: str) -> str:
    """The todo with an empty tag on the end: type the project and press enter.

    What alt+m puts in the bar. It starts the tag rather than filling it in, because
    the point of the key is to name a project, and the name you want is not usually
    the one already there -- and enter on the bare marker unfiles the todo, so the
    "no project" answer is a keystroke rather than nine backspaces.
    """
    return f"{text} {MARKER}"
