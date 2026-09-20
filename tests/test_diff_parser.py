from src.diff_parser import extract_changed_lines, parse_patch


def test_parse_patch_tracks_added_lines_and_ignores_deletions():
    patch = "@@ -1,4 +1,5 @@\n old = 1\n-password = 'old'\n+password = 'new'\n+print(password)\n end = True"
    result = parse_patch("app.py", patch)
    assert [(item.line, item.code) for item in result] == [(2, "password = 'new'"), (3, "print(password)")]
    assert result[0].language == "python"


def test_extract_changed_lines_handles_multiple_and_binary_files():
    result = extract_changed_lines([
        {"filename": "app.py", "patch": "@@ -2,0 +2,1 @@\n+print('x')"},
        {"filename": "logo.png", "patch": "Binary files differ"},
        {"filename": "generated.js"},
    ])
    assert len(result) == 1
    assert result[0].file == "app.py"
    assert result[0].line == 2


def test_empty_patch_is_safe():
    assert parse_patch("README.md", None) == []
