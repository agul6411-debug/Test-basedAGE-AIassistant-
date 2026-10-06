"""Tests for path sanitization and directory traversal prevention."""

from pathlib import Path

import pytest

from core.safety.path_validator import (
    PathTraversalError,
    get_data_path,
    sanitize_filename,
    validate_path_within_root,
)


def test_sanitize_filename_valid():
    assert sanitize_filename("test_layout.json") == "test_layout.json"
    assert sanitize_filename("my-document_123.txt") == "my-document_123.txt"


def test_sanitize_filename_rejects_empty():
    with pytest.raises(PathTraversalError):
        sanitize_filename("")
    with pytest.raises(PathTraversalError):
        sanitize_filename("   ")


def test_sanitize_filename_rejects_null_byte():
    with pytest.raises(PathTraversalError):
        sanitize_filename("test\x00file.txt")


def test_sanitize_filename_rejects_traversal():
    with pytest.raises(PathTraversalError):
        sanitize_filename("../secret.txt")
    with pytest.raises(PathTraversalError):
        sanitize_filename("folder/sub.txt")
    with pytest.raises(PathTraversalError):
        sanitize_filename("folder\\sub.txt")


def test_sanitize_filename_replaces_illegal_chars():
    result = sanitize_filename('test:*?"<>|file.txt')
    for ch in ':*?"<>|':
        assert ch not in result
    assert result == "test_______file.txt"


def test_validate_path_within_root_safe(tmp_path: Path):
    root = tmp_path / "sandbox"
    root.mkdir()
    target = root / "subdir" / "file.txt"
    target.parent.mkdir()
    target.write_text("ok")

    validated = validate_path_within_root("subdir/file.txt", root)
    assert validated.resolve() == target.resolve()


def test_validate_path_within_root_rejects_escape(tmp_path: Path):
    root = tmp_path / "sandbox"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")

    with pytest.raises(PathTraversalError):
        validate_path_within_root("../outside.txt", root)

    with pytest.raises(PathTraversalError):
        validate_path_within_root(outside, root)


def test_get_data_path_confinement(tmp_path: Path):
    safe_data = get_data_path("logs/test.log", project_root=tmp_path)
    assert safe_data.is_relative_to(tmp_path / "data")

    with pytest.raises(PathTraversalError):
        get_data_path("../../windows/system32/cmd.exe", project_root=tmp_path)
