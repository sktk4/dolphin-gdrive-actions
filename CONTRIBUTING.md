# Contributing

Thanks for trying dolphin-gdrive-actions. This is a small quality-of-life tool — issues and small PRs are welcome.

## Report a bug or request a feature

Use [GitHub Issues](https://github.com/sktk4/dolphin-gdrive-actions/issues). Pick the bug or feature template so we get the basics (OS, Plasma version, rclone setup, what you expected).

Helpful details:

- Output of `dga status`
- Whether the path is under a configured mount
- Plasma version and Wayland vs X11
- Relevant rclone remote type (personal Drive, shared drive, combine mount)

## Development

```bash
git clone https://github.com/sktk4/dolphin-gdrive-actions.git
cd dolphin-gdrive-actions
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

Read **[AGENTS.md](AGENTS.md)** before larger changes — it documents architecture, module map, and project conventions.

## Pull requests

- Keep Dolphin integration thin: new behavior belongs in the `dga` CLI first.
- Do not use `rclone link` in user-facing commands.
- Run `pytest` before opening a PR.
- One focused change per PR is easier to review.

## Scope

This project targets KDE Dolphin on Linux with rclone FUSE mounts. Out of scope for now: PyPI packaging polish, native Dolphin plugins, and non-Linux platforms.
