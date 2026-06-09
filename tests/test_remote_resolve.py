from dolphin_gdrive_actions.remote_resolve import (
    parse_combine_upstreams,
    rewrite_combine_remote_path,
)


def test_parse_combine_upstreams() -> None:
    raw = '"Legal=Legal:" "HR=HR:" "files=drive:important/files"'
    assert parse_combine_upstreams(raw) == {
        "Legal": "Legal:",
        "HR": "HR:",
        "files": "drive:important/files",
    }


def test_rewrite_combine_remote_path_to_upstream() -> None:
    upstreams = {"Legal": "Legal:", "HR": "HR:"}
    assert (
        rewrite_combine_remote_path("AllDrives:Legal/Working Files/file.pdf", upstreams)
        == "Legal:Working Files/file.pdf"
    )


def test_rewrite_combine_remote_path_with_upstream_prefix() -> None:
    upstreams = {"files": "drive:important/files"}
    assert (
        rewrite_combine_remote_path("combine:files/sub/file.txt", upstreams)
        == "drive:important/files/sub/file.txt"
    )


def test_rewrite_combine_remote_path_unknown_top_dir() -> None:
    upstreams = {"Legal": "Legal:"}
    assert rewrite_combine_remote_path("AllDrives:WorkAlias/file.pdf", upstreams) is None


def test_rewrite_combine_remote_path_top_level_dir() -> None:
    upstreams = {"Legal": "Legal:"}
    assert rewrite_combine_remote_path("AllDrives:Legal", upstreams) == "Legal:"
