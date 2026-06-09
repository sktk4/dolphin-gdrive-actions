# dolphin-gdrive-actions

Google Drive-style right-click actions for KDE Dolphin on files that live inside an rclone-mounted Google Drive.

KDE's native `kio-gdrive` integration can be unreliable for new setups because of Google API/OAuth issues. [rclone](https://rclone.org/) mounts Google Drive reliably as a normal filesystem, but it does not provide Drive context-menu actions in Dolphin. This project adds those actions starting with a service menu backed by a reusable CLI.

## Current status

**v0.2 prototype**

- `copy-link` — resolve a Drive file-ID URL and print it (does not change sharing permissions)
- `open` — resolve file ID and open in browser (standalone Chromium app window when available)
- `open-folder` — open the containing Google Drive folder in a Chromium app window when available (account auto-detected from rclone, like `new`)
- `offline` — best-effort offline access (browser for Google Workspace files; VFS cache warm for regular files)
- `config set` — optional: set per-mount `google_authuser` for `dga new` / `open-folder` when multiple Google accounts are signed in
- `new` — open a blank Google Doc, Sheet, Slide, or Drawing in the browser for the target folder (saved after you edit)
- `setup` — auto-detect rclone mounts, write config, install Dolphin service menus
- `uninstall` — remove everything `setup` installed (including legacy menu files)
- `status` — show what is installed and whether mounts look healthy

## Requirements

- Linux with KDE Plasma (developed on Kubuntu 26.04, Plasma 6, Wayland)
- Python 3.11+
- [rclone](https://rclone.org/) installed and configured with a working Google Drive remote
- An active rclone FUSE mount (for auto-detect during `dga setup`)

## How it works

1. `dga setup` detects active `fuse.rclone` mounts and writes config plus Dolphin service menus.
2. Dolphin's service menu calls `dga open <local_path>` using an absolute path to `dga`.
3. The backend translates the local path to `remote:path`.
4. The backend runs `rclone lsjson --stat` to read the Drive file ID (read-only; sharing unchanged).
5. On success, a file-ID URL is printed to stdout (add `--clipboard` to also copy it).
6. On failure, you get an actionable error (desktop notification when launched from Dolphin).

```
dga setup  →  config + icons + servicemenus + manifest
Local path under mount  →  remote:path  →  lsjson --stat  →  file-ID URL
dga uninstall  →  removes tracked files + config
```

**Security note:** Older versions used `rclone link`, which could change Drive sharing to "Anyone with the link." If you used `open` or `copy-link` before this fix, check **General access** in Drive for those files.

## Quick start

### 1. Install the CLI

```bash
cd dolphin-gdrive-actions
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Or, closer to an end-user install:

```bash
pip install --user .
```

Ensure `~/.local/bin` is on your `PATH`.

### 2. Set up integration

With your rclone mount active:

```bash
dga setup
```

This will:

- Auto-detect active `fuse.rclone` mounts (via `findmnt`, with fallbacks)
- Write `~/.config/dolphin-gdrive-actions/config.toml`
- Install custom menu icons into `~/.local/share/dolphin-gdrive-actions/icons/`
- Install service menus into `~/.local/share/kio/servicemenus/` with absolute `dga` and icon paths
- Write `~/.config/dolphin-gdrive-actions/install.toml` (used by `uninstall`)

If auto-detect cannot find mounts, pass explicit mappings:

```bash
dga setup --mount-root /home/you/Drives/personal --remote personal
```

Re-run with `--force` to overwrite an existing install.

### 3. Check status

```bash
dga status
```

### 4. Test from the terminal

```bash
dga copy-link "/home/you/Drives/personal/Misc/File.txt"
dga new doc "/home/you/Drives/personal/Projects"
```

On success, `copy-link` prints the Drive URL (add `--clipboard` to also copy it). `new doc` opens a blank Google Doc editor scoped to that folder in your browser.

### 5. Test in Dolphin

Right-click a file or folder and use the top-level Google Drive actions (KDE always lists TopLevel submenus before flat items):

1. **New Google Drive files** — submenu (Google Doc / Sheets / Slides / Drawings; uses theme icons — Dolphin does not reliably support custom submenu icons on Plasma 6)
2. *(divider)*
3. **Open with Google Drive**
4. **Copy Google Drive link**
5. **Open Google Drive folder** — opens the containing folder in Drive (use Drive's Share button there if needed)
6. **Google Drive offline access**
7. *(divider)*

Horizontal dividers bracket the four flat actions (not the submenu). See AGENTS.md for why submenu-last order is not achievable with service-menu `.desktop` files alone.

Menus appear for all files/folders (not only under configured mounts); actions outside a configured mount show an error notification.

After upgrading from an older install, refresh menus with:

```bash
dga setup --force
```

### 6. Uninstall integration

```bash
dga uninstall
```

This removes the install manifest, config, tracked icons, and service menu files. It does **not** remove the Python package.

To remove the CLI as well:

```bash
dga uninstall
pip uninstall dolphin-gdrive-actions
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Config/setup error, or path outside configured mounts |
| 3 | `rclone` not found on `PATH` |
| 4 | Drive metadata lookup failed |
| 6 | Failed to open the default browser |

## Limitations

- **Copy link / Open** resolve file-ID URLs only; they do not change Drive sharing permissions (same model as Mac/Windows Drive desktop). **Open** uses a standalone Chromium app window (`--app`) when the default browser is Chromium-based; otherwise it falls back to a normal browser tab.
- **Open Google Drive folder** opens the containing folder in a standalone Chromium app window (`--app`) when the default browser is Chromium-based; otherwise it falls back to a normal browser tab. Uses your existing Google login. The Google account is chosen automatically from the rclone remote's OAuth identity (same as **New Google Drive files**); optional override via `google_authuser` per mount. Shared-drive mount roots use rclone `team_drive` / alias options for the folder URL. There is no supported Drive URL to pre-highlight a specific file in the folder view. Use Drive's native Share button in the browser if you need to change permissions.
- **Available offline** is not the same as Google Drive for desktop offline sync. For regular files it only warms the rclone mount's VFS cache.
- **New Google Drive files** opens a blank Google Workspace editor in your browser for the target folder. The account is chosen automatically from the rclone remote's OAuth identity (e.g. work vs personal). Optional override: `dga config set google_authuser WorkDrive 1` (browser account index) or add `google_authuser = "you@work.com"` under a `[[mounts]]` entry.
- **Add shortcut** is not implemented yet.
- Menus are visible everywhere you right-click; only paths under configured mounts succeed.

## For contributors and agents

See **[AGENTS.md](AGENTS.md)** for architecture, module map, design decisions, known limitations, and handoff context. Read it before continuing development. Cursor loads `.cursor/rules/project.mdc` automatically in this repo.

## Development

Install dev dependencies and run tests:

```bash
pip install -e ".[dev]"
pytest
```

Clean setup/uninstall cycle during development:

```bash
pip install -e .
dga setup
dga status
dga uninstall
```

## Roadmap

- Open in browser (done via `dga open` and Dolphin menu)
- Share / manage sharing (use **Open Google Drive folder** then Drive's Share button in the browser)
- Add shortcut to Google Drive
- Success notifications for `open` / `copy-link`
- Mount-only menu visibility (requires native Dolphin plugin)
- PyPI / pipx distribution
- Future native Dolphin plugin or tray app reusing the same CLI contract

## Do not commit

Never commit your local `~/.config/rclone/rclone.conf`, `~/.config/dolphin-gdrive-actions/config.toml`, or LibreOffice `.odg` icon sources. Ship exported PNGs only.

## License

MIT — see [LICENSE](LICENSE).
