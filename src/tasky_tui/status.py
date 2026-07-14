"""What the line at the bottom of each screen says.

Every screen ends in a count of what is on it and a hint about the key that would do
something about it. That is all text, and text needs no running app to decide -- so it
is here, where it can be read at a glance and tested without one.
"""


def plural(count: int, noun: str) -> str:
    return noun if count == 1 else f"{noun}s"


def working_list(active: int, completed: int, project: str | None = None) -> str:
    # The counts are of the list in front of you, so in a project they count that
    # project. Saying which one is what keeps "1 active" from reading as a claim
    # about the whole list when it is a claim about a corner of it.
    summary = f"{active} active{_in(project)}"
    if completed:
        # Surface the backlog, so completed todos do not quietly pile up.
        summary += f" · {completed} completed (alt+a to archive)"
    return summary


def archive(shown: int, project: str | None = None) -> str:
    if not shown:
        return f"Nothing archived{_in(project)} yet · alt+v to go back"
    return f"{shown} archived {plural(shown, 'todo')}{_in(project)} · alt+u to restore one"


def projects(count: int, read_only: bool = False) -> str:
    if count:
        summary = f"{count} {plural(count, 'project')}"
    else:
        # "yet" is an invitation to make one, which the archive is not extending.
        summary = "No projects" if read_only else "No projects yet"
    if read_only:
        # Say why the keys the footer is not offering are not being offered.
        summary += " · archived, so read-only"
    return summary


def viewing(archived: bool, project: str | None) -> str:
    """What the header says you are looking at, when it is not simply your todos.

    The archive is a mode and a project is a filter, and you can be in both at once --
    the archive, one project at a time. So this says both rather than choosing.
    """
    parts = ["archive"] if archived else []
    if project:
        parts.append(project)
    return " · ".join(parts)


def _in(project: str | None) -> str:
    return f" in {project}" if project else ""


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
