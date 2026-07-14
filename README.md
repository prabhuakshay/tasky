# tasky

A task manager in your terminal, built with [Textual](https://textual.textualize.io/).

> **Status:** early days. The app currently starts up and quits; features are on the way.

## Install

```bash
pip install tasky-tui
```

The distribution is named `tasky-tui` because `tasky` was already taken on PyPI.
The command you run is still `tasky`.

## Usage

```bash
tasky
```

Press `alt+q` to quit.

## Development

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync          # install dependencies
uv run tasky     # run the app
```

## License

MIT — see [LICENSE](LICENSE).
