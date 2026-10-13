from vision.download_data import count_images


def test_count_images_counts_per_class_and_ignores_non_images(tmp_path):
    (tmp_path / "healthy").mkdir()
    (tmp_path / "rust").mkdir()
    (tmp_path / "empty").mkdir()
    (tmp_path / "healthy" / "a.jpg").touch()
    (tmp_path / "healthy" / "b.PNG").touch()
    (tmp_path / "healthy" / "notes.txt").touch()
    (tmp_path / "rust" / "c.jpeg").touch()
    (tmp_path / "stray_file.jpg").touch()

    assert count_images(tmp_path) == {"healthy": 2, "rust": 1}
