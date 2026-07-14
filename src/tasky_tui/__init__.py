from tasky_tui.app import TaskyApp

__all__ = ["TaskyApp", "main"]


def main() -> None:
    TaskyApp().run()
