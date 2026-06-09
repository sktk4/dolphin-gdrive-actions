from importlib.resources import files
from pathlib import Path

import pytest

from dolphin_gdrive_actions.integration import (
    _collect_top_level_action_keys,
    _file_sha256,
    _is_safe_to_remove,
    _remove_installed_file,
    cmd_setup,
    cmd_status,
    cmd_uninstall,
    install_icons,
    render_desktop_exec,
    render_desktop_template,
)
from dolphin_gdrive_actions.manifest import InstalledFile, InstallManifest, load_manifest, manifest_exists
from dolphin_gdrive_actions.paths_util import installed_icons_dir, servicemenu_dir


class Args:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


SERVICEMENUS = ("google-drive.desktop", "google-drive-new.desktop")
PACKAGED_ICONS = tuple(
    sorted(
        entry.name
        for entry in (files("dolphin_gdrive_actions.data") / "icons").iterdir()
        if entry.name.endswith(".png")
    )
)
LEGACY_SERVICEMENUS = (
    "open-with-google-drive.desktop",
    "google-drive-offline.desktop",
    "gd-01-block.desktop",
    "gd-02-copy.desktop",
    "gd-03-share.desktop",
    "gd-04-offline-block.desktop",
)


def test_render_desktop_exec() -> None:
    template = "Exec=dga open %f\nExec=dga open-folder %f\n"
    rendered = render_desktop_exec(template, Path("/usr/bin/dga"))
    assert rendered == "Exec=/usr/bin/dga open %f\nExec=/usr/bin/dga open-folder %f\n"


def test_render_desktop_template_substitutes_icons() -> None:
    template = (
        "Exec=dga open %f\n"
        "Icon=icon_gdrive_open.png\n"
        "Icon=icon_gdrive_link.png\n"
        "X-KDE-Submenu-Icon=icon_gdrive_new.png\n"
    )
    icon_paths = {
        "icon_gdrive_open.png": Path("/tmp/icons/icon_gdrive_open.png"),
        "icon_gdrive_link.png": Path("/tmp/icons/icon_gdrive_link.png"),
        "icon_gdrive_new.png": Path("/tmp/icons/icon_gdrive_new.png"),
    }
    rendered = render_desktop_template(template, Path("/usr/bin/dga"), icon_paths)
    assert rendered == (
        "Exec=/usr/bin/dga open %f\n"
        "Icon=/tmp/icons/icon_gdrive_open.png\n"
        "Icon=/tmp/icons/icon_gdrive_link.png\n"
        "X-KDE-Submenu-Icon=/tmp/icons/icon_gdrive_new.png\n"
    )


def test_install_icons_copies_packaged_pngs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_home = tmp_path / "data"
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

    installed, icon_paths = install_icons()

    assert len(installed) == len(PACKAGED_ICONS)
    assert set(icon_paths) == set(PACKAGED_ICONS)
    for name in PACKAGED_ICONS:
        destination = installed_icons_dir() / name
        assert destination.is_file()
        assert icon_paths[name] == destination
        entry = next(item for item in installed if item.source == name)
        assert entry.kind == "icon"
        assert entry.content == _file_sha256(destination)


def test_uninstall_removes_matching_icon_and_skips_modified(
    tmp_path: Path,
) -> None:
    icon_path = tmp_path / "icon_gdrive_open.png"
    icon_path.write_bytes(b"original")
    digest = _file_sha256(icon_path)
    installed = InstalledFile(
        path=icon_path,
        kind="icon",
        source="icon_gdrive_open.png",
        content=digest,
    )
    manifest = InstallManifest(
        version=1,
        dga_path=Path("/usr/bin/dga"),
        installed_at="2026-01-01T00:00:00+00:00",
        files=(installed,),
    )

    assert _remove_installed_file(installed, manifest) == "removed"
    assert not icon_path.exists()

    icon_path.write_bytes(b"modified")
    assert _remove_installed_file(installed, manifest) == f"Skipped modified file: {icon_path}"
    assert icon_path.exists()


def test_uninstall_skips_modified_file() -> None:
    installed = InstalledFile(
        path=Path("/tmp/menu.desktop"),
        kind="servicemenu",
        source="google-drive.desktop",
        content="Exec=/usr/bin/dga open %f\n",
    )
    manifest = InstallManifest(
        version=1,
        dga_path=Path("/usr/bin/dga"),
        installed_at="2026-01-01T00:00:00+00:00",
        files=(installed,),
    )
    modified = "Exec=/other/dga open %f\n"
    assert _is_safe_to_remove(modified, installed, manifest) is True
    assert _is_safe_to_remove("Exec=/bin/other open %f\n", installed, manifest) is False


@pytest.mark.parametrize(
    ("exec_line",),
    [
        ("Exec=/other/dga open-folder %f\n",),
        ("Exec=/other/dga offline %f\n",),
    ],
)
def test_uninstall_allows_refreshed_dga_path_for_new_commands(
    exec_line: str,
) -> None:
    installed = InstalledFile(
        path=Path("/tmp/menu.desktop"),
        kind="servicemenu",
        source="google-drive.desktop",
        content="Exec=/usr/bin/dga open-folder %f\n",
    )
    manifest = InstallManifest(
        version=1,
        dga_path=Path("/usr/bin/dga"),
        installed_at="2026-01-01T00:00:00+00:00",
        files=(installed,),
    )
    assert _is_safe_to_remove(exec_line, installed, manifest) is True


def _setup_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[Path, Path, Path]:
    config_home = tmp_path / "config"
    data_home = tmp_path / "data"
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    monkeypatch.setattr(
        "dolphin_gdrive_actions.mount_detect._read_mount_lines",
        lambda: [("personal:", str(mount_root))],
    )
    monkeypatch.setattr(
        "dolphin_gdrive_actions.integration.resolve_dga_path",
        lambda: Path("/usr/bin/dga"),
    )
    return config_home, data_home, mount_root


def test_setup_and_uninstall_cycle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_home, data_home, _mount_root = _setup_env(monkeypatch, tmp_path)
    servicemenus = data_home / "kio" / "servicemenus"

    assert cmd_setup(Args(mount_root=None, remote=None, force=False)) == 0
    assert manifest_exists()
    manifest = load_manifest()
    assert manifest.dga_path == Path("/usr/bin/dga")
    assert len(manifest.files) == len(SERVICEMENUS) + len(PACKAGED_ICONS)
    for name in SERVICEMENUS:
        menu_path = servicemenus / name
        assert menu_path.exists()
        content = menu_path.read_text(encoding="utf-8")
        if name == "google-drive.desktop":
            assert "Icon=icon_gdrive_open.png" not in content
            assert f"Icon={installed_icons_dir() / 'icon_gdrive_open.png'}" in content
        if name == "google-drive-new.desktop":
            assert "Icon=icon_gdrive_new.png" not in content
            assert "X-KDE-Submenu-Icon=" not in content
            assert "[Desktop Action 00newGoogleDriveFiles]" not in content
            assert "Icon=text-editor" in content
    for name in PACKAGED_ICONS:
        assert (installed_icons_dir() / name).exists()
    assert (config_home / "dolphin-gdrive-actions" / "config.toml").exists()

    assert cmd_status(Args()) == 0
    assert cmd_uninstall(Args()) == 0
    assert not manifest_exists()
    assert not (config_home / "dolphin-gdrive-actions" / "config.toml").exists()
    for name in SERVICEMENUS:
        assert not (servicemenus / name).exists()
    assert not installed_icons_dir().exists()


def test_servicemenu_template_action_key_order() -> None:
    from importlib.resources import files

    from dolphin_gdrive_actions.servicemenu_diag import diagnose_servicemenu

    menu = files("dolphin_gdrive_actions.data") / "servicemenus" / "google-drive.desktop"
    content = menu.read_text(encoding="utf-8")
    diagnosis = diagnose_servicemenu(menu)
    assert diagnosis["action_keys"] == [
        "_SEPARATOR_",
        "01openWithGoogleDrive",
        "02copyGoogleDriveLink",
        "03openDriveFolder",
        "04googleDriveOfflineAccess",
        "_SEPARATOR_",
        "99menuEnd",
    ]
    assert "\u200b" not in content
    assert "\uE010" not in content
    for name in (
        "Open with Google Drive",
        "Copy Google Drive link",
        "Open Google Drive folder",
        "Google Drive offline access",
    ):
        assert f"Name={name}" in content


def test_collect_top_level_action_keys_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _config_home, data_home, _mount_root = _setup_env(monkeypatch, tmp_path)
    assert cmd_setup(Args(mount_root=None, remote=None, force=False)) == 0

    keys = _collect_top_level_action_keys(data_home / "kio" / "servicemenus")
    assert keys == [
        "_SEPARATOR_",
        "01openWithGoogleDrive",
        "02copyGoogleDriveLink",
        "03openDriveFolder",
        "04googleDriveOfflineAccess",
        "_SEPARATOR_",
        "99menuEnd",
    ]


def test_setup_removes_legacy_servicemenus(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _config_home, data_home, _mount_root = _setup_env(monkeypatch, tmp_path)
    servicemenus = data_home / "kio" / "servicemenus"
    servicemenus.mkdir(parents=True)
    for name in LEGACY_SERVICEMENUS:
        (servicemenus / name).write_text("Exec=dga open %f\n", encoding="utf-8")

    assert cmd_setup(Args(mount_root=None, remote=None, force=False)) == 0
    for name in LEGACY_SERVICEMENUS:
        assert not (servicemenus / name).exists()


def test_uninstall_removes_legacy_servicemenus(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _config_home, data_home, _mount_root = _setup_env(monkeypatch, tmp_path)
    servicemenus = data_home / "kio" / "servicemenus"
    servicemenus.mkdir(parents=True)
    legacy = servicemenus / "google-drive.desktop"
    legacy.write_text("Exec=dga open %f\n", encoding="utf-8")

    assert cmd_uninstall(Args()) == 1
    assert not legacy.exists()
    assert servicemenu_dir() == servicemenus


def test_setup_refuses_without_force_when_installed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config_home = tmp_path / "config"
    data_home = tmp_path / "data"
    mount_root = tmp_path / "mount"
    mount_root.mkdir()
    config_dir = config_home / "dolphin-gdrive-actions"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text("[[mounts]]\n", encoding="utf-8")

    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))

    assert cmd_setup(Args(mount_root=[str(mount_root)], remote=["personal"], force=False)) == 2
