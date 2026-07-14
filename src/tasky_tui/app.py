from textual.app import App, ComposeResult
from textual.widgets import Footer, Header


class TaskyApp(App[None]):
    """Tasky's terminal UI."""

    TITLE = "tasky"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        ("alt+q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
