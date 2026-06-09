# Agent handoff: dolphin-gdrive-actions

This file is the onboarding doc for Cursor agents (or human contributors) continuing work on this repo. Read this before making changes.

Cursor also loads [.cursor/rules/project.mdc](.cursor/rules/project.mdc) (`alwaysApply: true`) with a short summary of these conventions.

## Project goal

Add **Google Drive-style right-click actions** to **KDE Dolphin** for files on an **rclone-mounted Google Drive**.

**Problem:** KDE `kio-gdrive` is unreliable for new setups (Google OAuth/API issues). **rclone** mounts Drive reliably as a normal filesystem but provides no Drive context-menu actions.

**Approach:** A reusable **Python CLI backend** (`dga`) plus thin **Dolphin service menus** (`.desktop` files). Dolphin only invokes the CLI; all logic lives in the backend so it can later power a tray app, native plugin, or Rust rewrite without changing the service-menu contract.

**Target environment:** Kubuntu 26.04, KDE Plasma 6.6.x, Dolphin on Wayland. Generalized for any Linux/KDE + rclone setup.

## Current status (v0.2 prototype)

### Implemented

| Command | Purpose |
|---------|---------|
| `dga copy-link <local_path>` | Map local path → `remote:path`, resolve file ID via `rclone lsjson --stat`, print share-style URL |
| `dga open <local_path>` | Same metadata lookup, open view URL in browser (Chromium `--app` window when available; tab via `webbrowser` fallback) |
| `dga open-folder <local_path>` | Resolve containing folder ID, open account-scoped `drive.google.com/drive/folders/...` in browser (My Drive fallback when root has no ID; shared-drive root from rclone `team_drive` / alias options) |
| `dga offline <local_path>` | Google Workspace: open Drive web UI; regular files: warm VFS cache + success notify |
| `dga config set google_authuser <remote> <index\|email>` | Optional: per-mount browser account override for `dga new` and `dga open-folder` |
| `dga new <doc\|sheet\|slide\|drawing> <local_path>` | Resolve target folder ID, open blank Google Workspace editor in browser (saved to Drive after user edits) |
| `dga setup` | Auto-detect FUSE mounts, write config, install service menus, write manifest |
| `dga uninstall` | Remove manifest, config, tracked service menus, legacy menu files (full clean slate) |
| `dga status` | Report install state, config, active mounts |

### Not implemented (roadmap)

- Add shortcut to Google Drive
- Success notifications for `open` / `copy-link` (offline already notifies on success)
- Mount-only menu visibility (requires native Dolphin plugin)
- Multi-account UX
- PyPI / pipx publishing
- Native Dolphin plugin

## Architecture

```
Dolphin service menu (.desktop)
    → dga open %f        (absolute path to dga written by setup)
        → config.toml     (mount root → remote mapping)
        → paths.py        (local path → remote:path)
        → rclone lsjson --stat  (read-only metadata lookup)
        → file-ID URL     (does not change Drive sharing permissions)
        → stdout URL      (clipboard opt-in via --clipboard)
```

**Design rule:** Keep Dolphin integration thin. New features = new CLI subcommands first; service menus call them.

**Security:** `open` and `copy-link` must **never** call `rclone link` or otherwise mutate Drive sharing permissions. They resolve a file-ID URL only; access is governed by existing ACLs (same as Mac/Windows Drive desktop). Prior versions used `rclone link`, which could widen sharing to "Anyone with the link" on accounts where Google allowed it — audit affected files in Drive if you used those commands before this fix.

### Module map

| Module | Responsibility |
|--------|----------------|
| [`cli.py`](src/dolphin_gdrive_actions/cli.py) | Argparse; dispatches subcommands |
| [`commands.py`](src/dolphin_gdrive_actions/commands.py) | `copy-link`, `open`, `open-folder`, `new`, `offline`, and `config set` orchestration |
| [`drive_metadata.py`](src/dolphin_gdrive_actions/drive_metadata.py) | Drive view/share/create URL building, `lsjson --stat` parsing |
| [`browser.py`](src/dolphin_gdrive_actions/browser.py) | `open_url_app` for `dga open` (Chromium `--app`); `open_url` for tab/window elsewhere |
| [`integration.py`](src/dolphin_gdrive_actions/integration.py) | `setup`, `uninstall`, `status` |
| [`config.py`](src/dolphin_gdrive_actions/config.py) | Load/validate `config.toml`; optional per-mount `google_authuser` |
| [`paths.py`](src/dolphin_gdrive_actions/paths.py) | Local → `remote:path`; `resolve_target_folder_remote_path` for `dga new` and `open-folder` |
| [`mount_detect.py`](src/dolphin_gdrive_actions/mount_detect.py) | Auto-detect `fuse.rclone` mounts |
| [`remote_resolve.py`](src/dolphin_gdrive_actions/remote_resolve.py) | Combine upstream path rewrite for metadata lookup fallback |
| [`rclone.py`](src/dolphin_gdrive_actions/rclone.py) | `lsjson --stat` wrapper (read-only; no `rclone link`) |
| [`manifest.py`](src/dolphin_gdrive_actions/manifest.py) | Install manifest read/write |
| [`paths_util.py`](src/dolphin_gdrive_actions/paths_util.py) | XDG paths for config, manifest, icons, servicemenus |
| [`clipboard.py`](src/dolphin_gdrive_actions/clipboard.py) | Best-effort Klipper (qdbus6/qdbus) / wl-copy / xclip |
| [`notify.py`](src/dolphin_gdrive_actions/notify.py) | `notify-send` for errors and success when non-TTY |
| [`errors.py`](src/dolphin_gdrive_actions/errors.py) | Exceptions with stable exit codes |
| [`data/`](src/dolphin_gdrive_actions/data/) | Packaged templates (servicemenus, icons, config example) |

### Packaged assets

Canonical templates live under `src/dolphin_gdrive_actions/data/` (shipped via `package-data` in `pyproject.toml`). Top-level `config/` and `servicemenus/` are pointers only — do not edit copies there without updating `data/`.

## Critical technical facts

### rclone path translation

- Metadata lookup **requires** `remote:path` (e.g. `personal:Misc/File.txt`).
- It **does not work** on mounted local paths (`/home/.../Misc/File.txt`).
- The backend must map `local_root` + relative path → `remote:relative`.
- **Do not use `rclone link`** in user-facing commands — it mutates Drive sharing permissions.

### rclone lsjson --stat output

- With `--stat`, rclone returns a **single JSON object** `{...}`, not an array.
- `parse_lsjson_stat()` accepts either a dict (real rclone output) or a one-element list (backward compatibility).

### Open Drive folder

- `dga open-folder` uses `resolve_target_folder_remote_path` (same folder targeting as `dga new`), then `stat_item_with_combine_fallback` for folder ID.
- Shared-drive mount roots resolve `team_drive` / `root_folder_id` from rclone config, including values embedded in alias `remote` option strings (e.g. `WorkDrive,team_drive=ID`).
- Opens `build_drive_folder_url` / `build_my_drive_url` with `authuser` via `open_url_app` (Chromium `--app` when available; tab via `open_url` fallback); empty folder ID at My Drive root falls back to account-scoped My Drive.
- Account selection matches `dga new`: per-mount `google_authuser` override, else auto-detect from rclone OAuth (following combine upstream aliases). Set `google_authuser` to avoid auto-detect latency when multiple accounts are signed in.
- No OAuth setup; uses the user's existing browser Google session. Sharing is via Drive's native UI after the folder opens.

### Mount auto-detect

- Primary: `findmnt -rn -t fuse.rclone -o SOURCE,TARGET`
- Fallbacks: `/proc/mounts`, `mount -t fuse.rclone`
- FUSE `SOURCE` may include rclone suffix: `personal{AbCdE}:` → normalized to `personal`
- `dga setup` installs **all** detected rclone mounts, not only Google Drive remotes

### Dolphin / environment

- Dolphin **does not** activate Python venvs or load shell profiles.
- `dga setup` writes an **absolute path** to `dga` in installed `.desktop` files and **absolute paths** to packaged PNG icons for main menu actions.
- Custom icons live in [`data/icons/`](src/dolphin_gdrive_actions/data/icons/). Templates reference basenames (e.g. `Icon=icon_gdrive_open.png`); setup copies PNGs to `~/.local/share/dolphin-gdrive-actions/icons/` and substitutes full paths. Main-block actions in [`google-drive.desktop`](src/dolphin_gdrive_actions/data/servicemenus/google-drive.desktop) use custom icons. **New Google Drive files** submenu keeps theme icons on Plasma 6 — Dolphin ignores `[Desktop Entry]` / `X-KDE-Submenu-Icon` and uses the first action's icon instead; no workaround without a visible duplicate entry. Spare packaged PNGs: `icon_gdrive_new.png`, `icon_gdrive_share.png`. Optional local LibreOffice source `*.odg` in `data/icons/` is gitignored (not shipped).
- Terminal `dga` requires venv activation, `pip install --user .`, or full path unless `~/.local/bin` has `dga`.
- **Dolphin menu uses `dga open`** — opens the default browser (visible feedback on success).
- **`copy-link` from terminal** prints the URL; clipboard is opt-in via `--clipboard`.
- **Failures** show a desktop notification via `notify-send`.
- **Offline success** also notifies when launched from Dolphin (non-TTY).
- Service menus use **`X-KDE-Priority=TopLevel`** for flat top-level items with `_SEPARATOR_` dividers in [`google-drive.desktop`](src/dolphin_gdrive_actions/data/servicemenus/google-drive.desktop).
- **New Google Drive files** is a TopLevel submenu in [`google-drive-new.desktop`](src/dolphin_gdrive_actions/data/servicemenus/google-drive-new.desktop) (`X-KDE-Submenu`); actions call `dga new doc|sheet|slide|drawing`. `dga new` auto-selects the Google account from each rclone remote's OAuth token, following combine-mount upstream aliases (override with optional `google_authuser` per mount).
- **Menu ordering (KDE limitation):** KIO inserts TopLevel service menus in fixed buckets — `userToplevelSubmenus` (files with `X-KDE-Submenu`) before `userToplevel` (flat actions without it). So **New Google Drive files** always appears above the four flat actions; there is no `.desktop`-only way to put a TopLevel submenu after TopLevel flat items. Within [`google-drive.desktop`](src/dolphin_gdrive_actions/data/servicemenus/google-drive.desktop), order is controlled by numbered action keys (`01…`, `02…`) and `_SEPARATOR_` dividers (KF6 groups and sorts within separator blocks). A native Dolphin plugin is the only path to arbitrary placement (e.g. submenu last).
- Menus show for all files/folders, not only under configured mounts (backend rejects out-of-mount paths).
- `dga setup` installs every `*.desktop` in packaged `data/servicemenus/`; `install.toml` tracks them for clean `dga uninstall`.
- Legacy menus (`open-with-google-drive.desktop`, `copy-google-drive-link.desktop`) are removed on setup and uninstall.

### Clipboard

- **Off by default.** Use `--clipboard` for best-effort copy.
- Klipper access tries **`qdbus6` then `qdbus`**, then `wl-copy` / `xclip` fallbacks.
- Clipboard failures do not fail the command (URL still printed, exit 0).
- When `--clipboard` is used from Dolphin (non-TTY), a clipboard failure shows an error notification.
- `ClipboardError` (exit 5) exists in `errors.py` but is currently unused.

## File locations (XDG)

| Path | Purpose |
|------|---------|
| `~/.config/dolphin-gdrive-actions/config.toml` | Mount mappings |
| `~/.config/dolphin-gdrive-actions/install.toml` | Install manifest (for uninstall) |
| `~/.local/share/dolphin-gdrive-actions/icons/*.png` | Installed menu icons |
| `~/.local/share/kio/servicemenus/*.desktop` | Installed Dolphin menus |

## Config format

```toml
[[mounts]]
local_root = "/home/you/Drives/personal"
remote = "personal"
# google_authuser = "1"  # optional; for dga new / open-folder when multiple Google accounts are signed in
```

- `google_authuser` is optional per mount; used by `dga new` and `dga open-folder` to pick the browser account (`dga config set google_authuser REMOTE INDEX_OR_EMAIL`).
- `remote` has no trailing colon in config; code adds `:` when building `remote:path`.
- Mount roots must exist when config is **loaded** (not only at setup).
- Longest `local_root` prefix wins when multiple mounts overlap.

## CLI exit codes (stable contract)

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Config/setup/path mapping error |
| 3 | `rclone` not on PATH |
| 4 | Drive metadata lookup failed (includes shortcuts/shared items with no resolvable ID) |
| 5 | Reserved (`ClipboardError`; unused while clipboard is best-effort) |
| 6 | Failed to open default browser |

## Dev workflow

```bash
cd dolphin-gdrive-actions
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest

# integration cycle
dga uninstall          # clean slate
dga setup              # auto-detect mounts + install menus
dga status
dga copy-link "/path/under/mount/file.pdf"
```

**PEP 668:** On Kubuntu, use venv or `pip install --user`; avoid system-wide `pip install`.

## Testing

- `tests/test_paths.py` — path translation
- `tests/test_mount_detect.py` — FUSE mount parsing, hash suffix stripping
- `tests/test_integration.py` — setup/uninstall cycle, legacy cleanup, desktop Exec rewrite, uninstall safety
- `tests/test_drive_metadata.py` — Drive URL building and lsjson parsing
- `tests/test_rclone_metadata.py` — `rclone lsjson --stat` wrapper
- `tests/test_remote_resolve.py` — combine upstream path rewrite
- `tests/test_commands_open_copy_link.py` — open/copy-link URL resolution and no-`rclone-link` regression
- `tests/test_commands_share_offline.py` — `open-folder` and `offline` command handlers
- `tests/test_commands_new.py` — `new` command folder targeting and create URLs
- `tests/test_config.py` — `google_authuser` parsing and `config set`
- `tests/test_browser.py` — default browser open

Run: `pytest` after code changes.

## Known limitations / tech debt

| Item | Notes |
|------|-------|
| Prior `rclone link` usage | Versions before the metadata-only fix could widen sharing; audit Drive "General access" on affected files |
| Combine mounts (e.g. AllDrives) | Metadata lookup retries via upstream rewrite when combine path fails |
| Open folder has no file highlight | Drive has no stable URL to pre-select a file in folder view; opens folder listing only |
| Offline is not Drive-for-desktop sync | Regular files: VFS cache warm only; Workspace files: open in browser |
| `dga new` opens browser editor only | Blank Workspace editor in browser; Google saves to Drive after user edits; rclone mount shows file after VFS refresh. Optional per-mount `google_authuser` (index or email) selects the browser account when multiple Google accounts are signed in. Drive directories omit ID in `lsjson --stat`; folder IDs are resolved via parent listing. |
| Add shortcut deferred | Would need destination picker + `rclone backend shortcut` |
| Menu visible everywhere | Service menus can't filter by mount path; backend errors on wrong paths |
| `dga setup` installs all rclone mounts | May include non-GDrive remotes; filter by remote type if needed later |
| `pip uninstall` ≠ `dga uninstall` | Documented; no pip hooks |
| Manifest TOML multiline | Content round-trip normalized via `rstrip` on load; manifest stores on-disk content |
| No PyPI release yet | Editable install / `pip install --user` only |

## Example dev system (reference only)

```
local_root: /home/you/Drives/personal
remote:     personal
translation: /home/you/Drives/personal/Misc/File.txt → personal:Misc/File.txt
```

Do not hardcode this username in code; use config.

## Adding a new action (pattern)

1. Add subcommand in `cli.py` + handler in `commands.py` (or new module).
2. Implement backend logic independent of Dolphin.
3. Add `.desktop` template under `data/servicemenus/`.
4. `dga setup` auto-installs all templates in that directory.
5. Add tests for pure logic; manual Dolphin test for integration.
6. Update README and this file.

## License

MIT — see [LICENSE](LICENSE).
