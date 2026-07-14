"""What the line at the bottom of each screen says.

Every screen ends in a count of what is on it and a hint about the key that would do
something about it. That is all text, and text needs no running app to decide -- so it
is here, where it can be read at a glance and tested without one.
"""


def plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"


def working_list(active: int, completed: int) -> str:
    summary = f"{active} active"
    if completed:
        # Surface the backlog, so completed todos do not quietly pile up.
        summary += f" · {completed} completed (alt+a to archive)"
    return summary


def archive(shown: int) -> str:
    if not shown:
        return "Nothing archived yet · alt+v to go back"
    return f"{shown} archived {plural(shown, 'todo')} · alt+u to restore one"


def notes(count: int, read_only: bool) -> str:
    if count:
        summary = f"{count} {plural(count, 'note')}"
    else:
        # "yet" is an invitation to write one, which the archive is not extending.
        summary = "No notes" if read_only else "No notes yet"
    if read_only:
        # Say why the keys the footer is not offering are not being offered.
        summary += " · archived, so read-only"
    return summary
