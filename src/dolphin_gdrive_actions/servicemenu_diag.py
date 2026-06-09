from __future__ import annotations

import re
from pathlib import Path


def diagnose_servicemenu(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {
            "path": str(path),
            "exists": False,
        }

    content = path.read_text(encoding="utf-8")
    actions_match = re.search(r"^Actions=(.+)$", content, re.MULTILINE)
    actions_line = actions_match.group(1) if actions_match else ""
    action_keys = [part for part in actions_line.split(";") if part]
    separator_tokens = actions_line.count("_SEPARATOR_")
    has_separator_section = "[Desktop Action _SEPARATOR_]" in content
    separator_name_match = re.search(
        r"\[Desktop Action _SEPARATOR_\]\s*\n(?:.*\n)*?Name=(.*)",
        content,
    )
    separator_name = separator_name_match.group(1).strip() if separator_name_match else None

    return {
        "path": str(path),
        "exists": True,
        "actions_line": actions_line,
        "action_keys": action_keys,
        "separator_tokens": separator_tokens,
        "has_separator_section": has_separator_section,
        "separator_name": separator_name,
        "separator_ready": separator_tokens > 0 and has_separator_section and bool(separator_name),
    }
