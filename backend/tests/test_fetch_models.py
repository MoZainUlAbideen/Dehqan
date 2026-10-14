from pathlib import Path

import pytest

from app.fetch_models import MODEL_FILES, ensure_models


def fake_downloader(calls, write=True):
    def download(repo_id: str, filename: str, dest_dir: Path) -> None:
        calls.append((repo_id, filename))
        if write:
            (dest_dir / filename).write_bytes(b"weights")

    return download


def test_downloads_only_missing_files(tmp_path):
    (tmp_path / MODEL_FILES[0]).write_bytes(b"already here")
    calls: list = []
    fetched = ensure_models("me/models", tmp_path, fake_downloader(calls))
    assert fetched == MODEL_FILES[1:] and calls == [("me/models", f) for f in MODEL_FILES[1:]]
    assert (tmp_path / MODEL_FILES[0]).read_bytes() == b"already here"  # untouched


def test_nothing_to_do_when_all_present(tmp_path):
    for f in MODEL_FILES:
        (tmp_path / f).write_bytes(b"x")
    calls: list = []
    assert ensure_models("me/models", tmp_path, fake_downloader(calls)) == [] and calls == []


def test_creates_the_directory(tmp_path):
    target = tmp_path / "nested" / "models"
    ensure_models("me/models", target, fake_downloader([]))
    assert all((target / f).exists() for f in MODEL_FILES)


def test_fails_loudly_if_the_repo_does_not_provide_a_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="did not provide"):
        ensure_models("me/models", tmp_path, fake_downloader([], write=False))
