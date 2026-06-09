# Reddit post drafts

Personal context: `kio-gdrive` did not work for me, so I use a **custom rclone setup** — configured and mounted manually, not through Dolphin/KIO integration.

## r/rclone

**Title:** Google Drive context-menu actions for KDE Dolphin on a manual rclone mount

**Body:**

KDE's `kio-gdrive` did not work for me, so I use a **custom rclone setup** — configured and mounted manually, not through Dolphin/KIO integration.

The mount itself is solid, but Dolphin still has no Drive-style right-click actions: no open in browser, copy link, new Doc in folder, etc.

I put together a small open-source helper for that gap: **[dolphin-gdrive-actions](https://github.com/sktk4/dolphin-gdrive-actions)** (MIT, v0.2 prototype).

After `dga setup` (it auto-detects active `fuse.rclone` mounts from your running setup), you get menu items like:

- New Google Doc / Sheet / Slide / Drawing in the target folder
- Open with Google Drive
- Copy Google Drive link (file-ID URL only — does **not** change sharing permissions)
- Open Google Drive folder
- Offline access (VFS cache warm for regular files)

Screenshot: https://github.com/sktk4/dolphin-gdrive-actions/raw/main/docs/screenshots/dolphin-context-menu.png

**Install (quick):**

```bash
git clone https://github.com/sktk4/dolphin-gdrive-actions.git
cd dolphin-gdrive-actions
pip install --user .
dga setup   # with your rclone mount running
```

Built on Kubuntu 26.04 / Plasma 6 / Wayland with my own manual rclone workflow. Early prototype — menus show everywhere but only work under configured mounts. No PyPI package yet.

Feedback welcome, especially from others on manual/custom rclone mounts (combine remotes, shared drives, multiple accounts). GitHub issues: https://github.com/sktk4/dolphin-gdrive-actions/issues

## r/kde (optional cross-post)

**Title:** Dolphin service menu: Google Drive actions for rclone-mounted Drive folders

**Body:** Same as above, but open with:

`kio-gdrive` never worked for me on my setup, so I run Google Drive through a **manually configured rclone mount** instead. Dolphin treats it like a normal folder, but without Drive context-menu actions…

## Before posting

- Check subreddit karma/account requirements
- Post to r/rclone first (best audience fit)
- Wait before cross-posting to r/kde
