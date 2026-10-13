import pytest

from vision.classes import CLASS_TO_INDEX, PLANTDOC_TO_PLANTVILLAGE, SHARED_CLASSES
from vision.samples import plantdoc_samples, plantvillage_samples
from vision.metrics import accuracy, macro_f1, majority_baseline_accuracy


def test_mapping_is_one_to_one_and_indices_are_stable():
    assert len(set(PLANTDOC_TO_PLANTVILLAGE.values())) == len(PLANTDOC_TO_PLANTVILLAGE) == 27
    assert SHARED_CLASSES == sorted(SHARED_CLASSES)
    assert CLASS_TO_INDEX[SHARED_CLASSES[0]] == 0


def test_plantvillage_samples_filters_by_split_and_caps_per_class(tmp_path):
    cls = SHARED_CLASSES[0]
    (tmp_path / cls).mkdir()
    for i in range(5):
        (tmp_path / cls / f"train_{i:05d}.jpg").touch()
    (tmp_path / cls / "test_00000.jpg").touch()
    for other in SHARED_CLASSES[1:]:
        (tmp_path / other).mkdir()

    train = plantvillage_samples(tmp_path, "train", max_per_class=3)
    test = plantvillage_samples(tmp_path, "test", max_per_class=None)

    assert len(train) == 3 and all(label == 0 for _, label in train)
    assert [p.name for p, _ in test] == ["test_00000.jpg"]


def test_plantdoc_samples_use_shared_label_and_skip_unmapped(tmp_path):
    (tmp_path / "Apple leaf").mkdir()
    (tmp_path / "Apple leaf" / "doc_00000.jpg").touch()
    (tmp_path / "Tomato two spotted spider mites leaf").mkdir()
    (tmp_path / "Tomato two spotted spider mites leaf" / "doc_00001.jpg").touch()

    samples = plantdoc_samples(tmp_path)

    assert len(samples) == 1
    assert samples[0][1] == CLASS_TO_INDEX["Apple___healthy"]


def test_metrics():
    y_true = [0, 0, 1, 1]
    y_pred = [0, 1, 1, 1]
    assert accuracy(y_true, y_pred) == 0.75
    assert macro_f1(y_true, y_pred) == pytest.approx((2 / 3 + 0.8) / 2)
    assert majority_baseline_accuracy([1, 1, 0], y_true) == 0.5
